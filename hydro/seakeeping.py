"""
Nonlinear time-domain roll dynamics
===================================

Solves the single-degree-of-freedom roll equation of motion

    I_xx · φ̈  +  b · φ̇  +  Δ·g · GZ(φ)  =  M_wave(t)

where

    I_xx    rolling moment of inertia about the longitudinal centroid
            (kg·m²)             ≈ Δ · k_xx²,    k_xx = C_roll · B
    b       linear viscous-roll damping (N·m·s)
            parameterised by the damping ratio ζ (critical = 1)
            b = 2·ζ·ωₙ·I_xx
    Δ       displacement mass (kg)
    GZ(φ)   righting-lever curve, piecewise-smooth interpolant of the
            solver's polygon-clip outputs (m), extended symmetrically
            for φ < 0 since monohull GZ is odd in φ
    M_wave  external wave excitation (N·m)

This is exactly the nonlinear restoring dynamics used in seakeeping
codes (SHIPFLOW, Octopus, Ulstein).  It is the time-domain counterpart
of a linear-seakeeping RAO at large amplitudes.

Three excitation modes:
    ``calm``  – no external moment (free roll decay)
    ``beam``  – sinusoidal beam-sea moment   M = A · sin(2π t / T)
    ``rogue`` – Gaussian pulse at t = duration / 4 (rogue-wave strike)

Capsize detection:  the solver flags the ship capsized when |φ| exceeds
the angle of vanishing stability (AVS) taken from the solver's GZ curve.

All outputs are packed into a `RollSimResult` dataclass.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Callable, Literal

from scipy.integrate import solve_ivp
from scipy.interpolate import PchipInterpolator


# ---------------------------------------------------------------------------

g = 9.80665   # standard gravity, m/s²


@dataclass
class RollSimResult:
    t:              np.ndarray    # time samples (s)
    phi:            np.ndarray    # heel angle (rad)
    phi_dot:        np.ndarray    # angular velocity (rad/s)
    M_wave:         np.ndarray    # external moment (N·m)
    capsized:       bool
    capsize_time_s: float         # seconds (inf if never)
    max_heel_deg:   float
    period_s:       float         # natural roll period Tφ
    zeta:           float         # damping ratio
    omega_n:        float         # natural angular freq ωₙ (rad/s)
    avs_used_deg:   float         # capsize threshold used
    mode:           str
    I_xx:           float         # rolling moment of inertia (kg·m²)
    mass_kg:        float


# ---------------------------------------------------------------------------

def _gz_odd_extension(angles_deg: np.ndarray,
                      gz_m: np.ndarray) -> PchipInterpolator:
    """
    Build a monotone piecewise-cubic Hermite interpolant of GZ(φ) for φ ∈ rad,
    extended to negative heel via the odd-symmetry  GZ(-φ) = -GZ(φ)  that
    holds for every symmetric monohull.
    """
    angles_deg = np.asarray(angles_deg, dtype=float)
    gz_m       = np.asarray(gz_m,       dtype=float)
    if angles_deg[0] != 0.0:
        # Prepend origin if missing
        angles_deg = np.insert(angles_deg, 0, 0.0)
        gz_m       = np.insert(gz_m,       0, 0.0)
    # Mirror to negative heel
    neg_ang = -angles_deg[::-1][:-1]
    neg_gz  = -gz_m[::-1][:-1]
    ang_full = np.concatenate([neg_ang, angles_deg])
    gz_full  = np.concatenate([neg_gz,  gz_m])
    return PchipInterpolator(np.radians(ang_full), gz_full, extrapolate=False)


def _wave_moment(mode: str,
                 amplitude_Nm: float,
                 period_s: float,
                 duration_s: float) -> Callable[[float], float]:
    if mode == "calm":
        return lambda t: 0.0
    if mode == "beam":
        if period_s <= 0:
            return lambda t: 0.0
        w = 2.0 * np.pi / period_s
        return lambda t: amplitude_Nm * np.sin(w * t)
    if mode == "rogue":
        t0    = duration_s * 0.25
        sigma = 1.5
        return lambda t: amplitude_Nm * np.exp(-0.5 * ((t - t0) / sigma) ** 2)
    raise ValueError(f"Unknown wave mode: {mode!r}")


# ---------------------------------------------------------------------------

def simulate_roll(
    gz_angles_deg : np.ndarray,
    gz_values_m   : np.ndarray,
    displacement_t: float,
    B_m           : float,
    GM_m          : float,
    phi0_deg      : float = 20.0,
    phi_dot0_degps: float = 0.0,
    duration_s    : float = 60.0,
    mode          : Literal["calm", "beam", "rogue"] = "calm",
    wave_amp_Nm   : float = 0.0,
    wave_period_s : float = 10.0,
    C_roll        : float = 0.35,
    zeta          : float = 0.05,
    n_points      : int   = 600,
    avs_deg       : float | None = None,
) -> RollSimResult:
    """
    Simulate rigid-body roll of the ship starting from (phi0, phi_dot0).

    Parameters
    ----------
    gz_angles_deg, gz_values_m
        GZ curve from the solver.  Angles must start at 0 and be
        monotonically increasing.  GZ is extended to negative heel
        using the odd-symmetry of monohull restoring levers.
    displacement_t
        Displacement Δ (tonnes, 1 t = 1000 kg).
    B_m, GM_m
        Breadth and initial GM (for k_xx and ωₙ).
    phi0_deg, phi_dot0_degps
        Initial conditions: release heel (°) and angular rate (°/s).
    duration_s
        Simulation horizon.
    mode
        'calm' – free decay; 'beam' – sinusoidal beam sea;
        'rogue' – single Gaussian pulse.
    wave_amp_Nm
        Peak external moment (N·m).  Scale tip: 1 MN·m = 1e6 N·m.
    wave_period_s
        Beam-sea period.  Resonance with Tφ = 2π/ωₙ maximises heel.
    C_roll
        Radius-of-gyration coefficient   k_xx = C_roll · B.
        Typical:  0.33 fine hulls, 0.35 displacement ships, 0.40 full.
    zeta
        Roll damping ratio (fraction of critical).  0.03 – 0.10 for ships.
    n_points
        Number of output samples (cosmetic; ODE uses adaptive step).
    avs_deg
        Angle of vanishing stability.  If None, taken from the extrapolated
        GZ curve (last zero-crossing of GZ on the positive side).
    """
    mass_kg = float(displacement_t) * 1000.0
    k_xx    = C_roll * float(B_m)
    I_xx    = mass_kg * k_xx ** 2

    Delta_weight = mass_kg * g        # N,  = Δ·g

    # Natural frequency (small-angle):   ωₙ² = Δ·g·GM / I_xx  = g·GM / k_xx²
    if GM_m > 0.0:
        omega_n = np.sqrt(g * GM_m) / k_xx
    else:
        # Unstable upright – pick a representative value from mid-heel slope
        omega_n = 0.1
    period_s = 2.0 * np.pi / omega_n if omega_n > 1e-6 else float("nan")
    b        = 2.0 * zeta * omega_n * I_xx     # N·m·s

    # GZ interpolant (odd-extended)
    gz_interp = _gz_odd_extension(gz_angles_deg, gz_values_m)
    phi_max_data = np.radians(np.max(np.abs(gz_angles_deg)))
    gz_max_abs   = float(np.max(np.abs(gz_values_m)))

    def gz_fn(phi: float) -> float:
        """
        Inside GZ data: PCHIP interpolation.
        Past the last datum: linear ramp to a strongly negative (capsizing)
        value of magnitude GZ_max at (φ_max_data + 30°) and held there.
        Ensures that once the ship exceeds AVS it actually keeps rolling
        over instead of frozen by a zero moment.
        """
        if abs(phi) < phi_max_data:
            return float(gz_interp(phi))
        # outside data range
        excess = abs(phi) - phi_max_data                 # rad, ≥ 0
        ramp   = min(1.0, excess / np.radians(30.0))     # 0 → 1 over 30°
        # Negative for +φ, positive for −φ  (capsizing torque opposes upright)
        return -np.sign(phi) * gz_max_abs * ramp

    # Determine AVS
    if avs_deg is None:
        # find first angle > max-GZ heel where GZ crosses zero on positive side
        ang_pos = np.asarray(gz_angles_deg, dtype=float)
        gz_pos  = np.asarray(gz_values_m,   dtype=float)
        # crossing from + to –
        avs_deg = float(ang_pos[-1])   # default = last angle
        for i in range(1, len(gz_pos)):
            if gz_pos[i - 1] > 0.0 and gz_pos[i] <= 0.0:
                # linear interp
                frac = gz_pos[i - 1] / (gz_pos[i - 1] - gz_pos[i])
                avs_deg = float(ang_pos[i - 1] + frac * (ang_pos[i] - ang_pos[i - 1]))
                break

    avs_rad = np.radians(avs_deg)
    M_wave_fn = _wave_moment(mode, wave_amp_Nm, wave_period_s, duration_s)

    # ODE right-hand side
    def rhs(t, y):
        phi, phi_dot = y
        M_rest = Delta_weight * gz_fn(phi)          # N·m restoring
        M_ext  = M_wave_fn(t)
        phi_ddot = (M_ext - b * phi_dot - M_rest) / I_xx
        return [phi_dot, phi_ddot]

    # Capsize event:  |phi| first crosses AVS  (not terminal – keep simulating)
    def event_capsize(t, y):
        return avs_rad - abs(y[0])
    event_capsize.terminal = False
    event_capsize.direction = -1

    # Terminal event:  ship rolled past ±180° (fully upside down, physics over)
    def event_fullrollover(t, y):
        return np.pi - abs(y[0])        # zero crossing at ±180°
    event_fullrollover.terminal = True
    event_fullrollover.direction = -1

    y0      = [np.radians(phi0_deg), np.radians(phi_dot0_degps)]
    t_eval  = np.linspace(0.0, duration_s, int(n_points))

    sol = solve_ivp(
        rhs, (0.0, duration_s), y0,
        t_eval=t_eval, events=[event_capsize, event_fullrollover],
        rtol=1e-6, atol=1e-8, method="RK45",
        max_step=0.25,
    )

    phi     = sol.y[0]
    phi_dot = sol.y[1]
    M_wave_arr = np.array([M_wave_fn(t) for t in sol.t])

    max_heel_deg = float(np.max(np.abs(np.degrees(phi))))
    if len(sol.t_events[0]) > 0:
        capsize_time = float(sol.t_events[0][0])
        capsized     = True
    else:
        capsize_time = float("inf")
        capsized     = max_heel_deg >= avs_deg
    # If fully rolled over, cap the max-heel reporting at 180°
    if max_heel_deg > 180.0:
        max_heel_deg = 180.0

    return RollSimResult(
        t=sol.t, phi=phi, phi_dot=phi_dot,
        M_wave=M_wave_arr,
        capsized=capsized, capsize_time_s=capsize_time,
        max_heel_deg=max_heel_deg,
        period_s=period_s, zeta=zeta, omega_n=omega_n,
        avs_used_deg=float(avs_deg), mode=mode,
        I_xx=I_xx, mass_kg=mass_kg,
    )

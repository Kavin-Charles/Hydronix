"""
Headless capsize-simulator demo.

Runs three scenarios on the KCS hull and prints a compact verdict table:

    1. Calm-water free decay from 25 degrees
    2. Resonant beam-sea (wave period tuned to roll natural period)
    3. Rogue-wave Gaussian pulse

Usage:
    python scripts/capsize_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hydro.io_formats    import load
from hydro.hydrostatics  import Hydrostatics
from hydro.heeled        import gz_curve_true
from hydro.seakeeping    import simulate_roll


def main() -> None:
    hull_path = ROOT / "samples" / "kcs_real.json"
    if not hull_path.exists():
        print(f"Missing {hull_path}. Run: python samples/build_kcs.py")
        sys.exit(1)

    hull  = load(str(hull_path))
    draft = 10.8
    KG    = 13.5

    hydro = Hydrostatics(hull, draft=draft, KG=KG)
    angles = list(range(0, 61, 5))
    ang, gz = gz_curve_true(hull, draft=draft, KG=KG, angles_deg=angles)

    print(f"\nKCS capsize-simulator demo")
    print(f"  L={hull.L:.1f} m,  B={hull.B_max:.2f} m,  T={draft} m")
    print(f"  Displacement={hydro.displacement:.1f} t,  GM={hydro.GM:.3f} m")
    print(f"  Natural roll period Tphi ~= {hydro.roll_period():.2f} s")
    print()

    scenarios = [
        dict(name="Free decay (calm)",      mode="calm",  phi0_deg=25.0,
             duration_s=120.0, wave_amp_Nm=0.0, wave_period_s=10.0),
        dict(name="Beam sea (resonant)",    mode="beam",  phi0_deg=0.0,
             duration_s=120.0, wave_amp_Nm=1.2e8,
             wave_period_s=hydro.roll_period()),
        dict(name="Rogue-wave pulse",       mode="rogue", phi0_deg=0.0,
             duration_s=120.0, wave_amp_Nm=3.5e8, wave_period_s=10.0),
    ]

    header = f"  {'Scenario':<22} | {'Capsized':>8} | {'max |phi|':>10} | {'t_cap':>8}"
    rule   = "  " + "-" * (len(header) - 2)
    print(header)
    print(rule)

    for sc in scenarios:
        r = simulate_roll(
            gz_angles_deg = ang,
            gz_values_m   = gz,
            displacement_t= hydro.displacement,
            B_m           = hull.B_max,
            GM_m          = hydro.GM,
            phi0_deg      = sc["phi0_deg"],
            duration_s    = sc["duration_s"],
            mode          = sc["mode"],
            wave_amp_Nm   = sc["wave_amp_Nm"],
            wave_period_s = sc["wave_period_s"],
        )
        tcap = f"{r.capsize_time_s:6.1f} s" if r.capsized else "  ---  "
        flag = "YES" if r.capsized else "no"
        print(f"  {sc['name']:<22} | {flag:>8} | {r.max_heel_deg:>8.1f} deg | {tcap:>8}")

    print()
    print("  AVS used =", f"{r.avs_used_deg:.1f} deg")
    print("  Ixx      =", f"{r.I_xx:.3e} kg m^2")
    print()


if __name__ == "__main__":
    main()

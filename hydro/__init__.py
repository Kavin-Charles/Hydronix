"""
HydroHackathon – First-principles ship hydrostatics & stability.

Modules
-------
integration   : Naval-architecture numerical integration (Simpson 1/3, 3/8, 5-8-(-1))
hull          : Hull geometry representation (stations, waterlines, offsets, sections)
hydrostatics  : Upright hydrostatic properties (∇, Aw, LCB, LCF, KB, BM, GM …)
heeled        : TRUE heeled hydrostatics by polygon clipping (no wall-sided assumption)
stability     : GZ curves, KN cross-curves, stability parameters
imo           : IMO 2008 IS Code intact-stability criteria checker (Part A)
trim          : Equilibrium trim solver (Newton–Raphson on T_mean, trim)
bonjean       : Bonjean curves – sectional area versus draft
free_surface  : Free-surface moment correction for liquid tanks
weather       : Weather criterion (wind heeling) per IMO A.749
io_formats    : CSV / Excel / JSON loaders
benchmarks    : Analytical and reference-hull test cases (box barge, Wigley)
report        : PDF report generation (reportlab)
plots         : High-quality matplotlib figures for the report
plots3d       : Interactive Plotly 3-D hull visualisation
seakeeping    : Nonlinear time-domain roll ODE (capsize simulator)
"""

from .hull          import Hull
from .hydrostatics  import Hydrostatics, hydrostatic_table
from .heeled        import HeeledHydrostatics, gz_curve_true, kn_curve_true
from .stability     import stability_parameters, gz_curve_wallsided
from .imo           import imo_intact_stability_check
from .trim          import solve_equilibrium
from .bonjean       import bonjean_curves
from .free_surface  import fsm_rectangular_tank, gm_corrected
from .seakeeping    import simulate_roll, RollSimResult

__version__ = "1.1.0"

__all__ = [
    "Hull",
    "Hydrostatics", "hydrostatic_table",
    "HeeledHydrostatics", "gz_curve_true", "kn_curve_true",
    "stability_parameters", "gz_curve_wallsided",
    "imo_intact_stability_check",
    "solve_equilibrium",
    "bonjean_curves",
    "fsm_rectangular_tank", "gm_corrected",
    "simulate_roll", "RollSimResult",
]

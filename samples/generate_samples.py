"""
Generate standard benchmark sample files used by the validation suite.

Produces:
    box_barge.json        60 × 12 × 6 m rectangular prism
    wigley_hull.json      100 × 10 × 6.25 m Wigley parabolic hull
    series60_cb070.csv    (wide form example, approximate)
"""

from __future__ import annotations
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from hydro.benchmarks import box_barge, wigley_hull
from hydro.io_formats import save_json, save_csv_wide


def main():
    bb = box_barge(L=60, B=12, D=6, n_stations=21, n_waterlines=13,
                   name="Box Barge 60×12×6")
    save_json(bb, HERE / "box_barge.json", draft=3.0, KG=3.0)

    wg = wigley_hull(L=100, B=10, D=6.25, n_stations=41, n_waterlines=21,
                     name="Wigley Hull L100")
    save_json(wg, HERE / "wigley_hull.json", draft=4.0, KG=3.5)

    # CSV export of the Wigley hull (wide form) for CSV-input demo
    save_csv_wide(wg, HERE / "wigley_hull.csv")

    print("Wrote:")
    for f in ("box_barge.json", "wigley_hull.json", "wigley_hull.csv"):
        print(f"  samples/{f}")


if __name__ == "__main__":
    main()

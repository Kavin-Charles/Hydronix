"""
Multi-format ship-offset file I/O
=================================

Supported inputs:

  * JSON   –  the native format (see sample_ship.json)
  * CSV    –  long-form with columns {station, waterline, half_breadth}
             *or* wide-form with the first row = waterline heights and the
             first column = station positions, body cells = half-breadths.
  * XLSX   –  Excel workbook following the wide-form convention.

Outputs:

  * to_csv / to_json   – round-trip utilities for the Hull object
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from .hull import Hull


# ---------------------------------------------------------------------------

def _wide_frame_to_hull(df: pd.DataFrame, name: str, rho: float) -> Hull:
    """First col = stations (m, from AP), first row (col-headers) = waterlines (m)."""
    stations   = df.iloc[:, 0].to_numpy(dtype=float)
    waterlines = np.array([float(c) for c in df.columns[1:]])
    half_br    = df.iloc[:, 1:].to_numpy(dtype=float)
    return Hull(stations, waterlines, half_br, name=name, rho=rho)


def _long_frame_to_hull(df: pd.DataFrame, name: str, rho: float) -> Hull:
    stations   = np.sort(df["station"].unique().astype(float))
    waterlines = np.sort(df["waterline"].unique().astype(float))
    hb = np.zeros((len(stations), len(waterlines)))
    for _, row in df.iterrows():
        i = int(np.where(stations   == float(row["station"]))[0][0])
        j = int(np.where(waterlines == float(row["waterline"]))[0][0])
        hb[i, j] = float(row["half_breadth"])
    return Hull(stations, waterlines, hb, name=name, rho=rho)


# ---------------------------------------------------------------------------

def load(path: str | Path, rho: float = 1.025) -> Hull:
    """
    Dispatch loader based on file extension.

    JSON must contain {stations, waterlines, half_breadths, ship_name?, rho?}.
    Additional keys (draft, KG) are ignored here – they're run-time inputs
    consumed by the CLI/app.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    ext = p.suffix.lower()
    if ext == ".json":
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        return Hull.from_dict({**data, "rho": data.get("rho", rho)})

    if ext in (".csv", ".tsv"):
        sep = "\t" if ext == ".tsv" else ","
        # Detect long vs wide by column names
        df = pd.read_csv(p, sep=sep)
        lc = {c.lower() for c in df.columns}
        if {"station", "waterline", "half_breadth"}.issubset(lc):
            df.columns = [c.lower() for c in df.columns]
            return _long_frame_to_hull(df, name=p.stem, rho=rho)
        return _wide_frame_to_hull(df, name=p.stem, rho=rho)

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(p, sheet_name=0)
        return _wide_frame_to_hull(df, name=p.stem, rho=rho)

    raise ValueError(f"Unsupported extension {ext!r}")


# ---------------------------------------------------------------------------

def save_json(hull: Hull, path: str | Path, draft: float | None = None,
              KG: float | None = None) -> None:
    d = hull.to_dict()
    if draft is not None:
        d["draft"] = draft
    if KG is not None:
        d["KG"] = KG
    Path(path).write_text(json.dumps(d, indent=2), encoding="utf-8")


def save_csv_wide(hull: Hull, path: str | Path) -> None:
    cols = ["station"] + [f"{z}" for z in hull.waterlines]
    df = pd.DataFrame(
        np.column_stack([hull.stations, hull.half_breadths]),
        columns=cols,
    )
    df.to_csv(path, index=False)

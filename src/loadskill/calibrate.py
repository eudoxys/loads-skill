"""Rescale county loads to known energy or peak values.

`loads.Calibrate` exists, but read the reference before relying on it:

- `Calibrate(load, energy={...})` without `peak` raises (it calls
  `peak.keys()` on `None`); pass `peak={}` too.
- string `start`/`end` hit `pd.datetime`, which pandas removed; pass
  `pd.Timestamp`s.
- its energy fit is *not* proportional: `fit_load` keeps the peak fixed and
  moves the minimum until the energy matches, which reshapes the load.
  The proportional rule in the module docstring is what most studies want,
  and is what `scale_to_energy` does.
- `Calibrate.load(state, year)` calls `Residential(state, county, year)`
  positionally, which `Residential` does not accept, so it fails.

These helpers are pure pandas, apart from `fit_energy_peak`, which delegates
to `loads.calibrate.fit_load` (no network).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _window(frame: pd.DataFrame, start, end) -> pd.Series:
    mask = pd.Series(True, index=frame.index)
    if start is not None:
        mask &= frame.index >= pd.Timestamp(start, tz=frame.index.tz) if pd.Timestamp(start).tzinfo is None \
            else frame.index >= pd.Timestamp(start)
    if end is not None:
        mask &= frame.index <= pd.Timestamp(end, tz=frame.index.tz) if pd.Timestamp(end).tzinfo is None \
            else frame.index <= pd.Timestamp(end)
    return mask


def scale_to_energy(
    frame: pd.DataFrame,
    targets: dict[str, float],
    *,
    start=None,
    end=None,
    also_scale: dict[str, list[str]] | None = None,
    recompute_net: bool = True,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Proportionally rescale columns so their energy over [`start`, `end`]
    equals `targets[column]` in MWh: P_new = P_old * E_new / E_old.

    The factor is applied to the whole frame (not only the window), so the
    window is where the energy is matched. `also_scale={"elec_total_MW":
    ["elec_residential_MW", ...]}` applies the same factor to sector columns
    so the sector sum still holds. With `recompute_net`, `elec_net_MW` is
    recomputed from total and DG. Returns the new frame and the factors.
    """
    out = frame.copy()
    window = _window(frame, start, end)
    factors: dict[str, float] = {}
    for col, target in targets.items():
        old = float(frame.loc[window, col].sum())
        if old == 0:
            raise ValueError(f"{col} has zero energy in the window; cannot scale")
        k = float(target) / old
        factors[col] = k
        for c in [col] + list((also_scale or {}).get(col, [])):
            out[c] = frame[c] * k
    if recompute_net and {"elec_net_MW", "elec_total_MW", "elec_dg_MW"} <= set(out.columns):
        out["elec_net_MW"] = out["elec_total_MW"] + out["elec_dg_MW"]
    return out, factors


def scale_monthly(
    frame: pd.DataFrame,
    column: str,
    monthly_mwh: pd.Series,
    *,
    also_scale: list[str] | None = None,
    recompute_net: bool = True,
) -> tuple[pd.DataFrame, pd.Series]:
    """Match each calendar month's energy to `monthly_mwh` (indexed by month
    start, same tz as the frame), e.g. a county's share of EIA-861M retail
    sales. Returns the frame and the monthly factors. Months absent from
    `monthly_mwh` keep factor 1."""
    out = frame.copy()
    month = frame.index.to_period("M") if frame.index.tz is None else frame.index.tz_convert(None).to_period("M")
    old = frame[column].groupby(month).sum()
    target = monthly_mwh.copy()
    target.index = pd.DatetimeIndex(target.index).tz_localize(None).to_period("M") \
        if pd.DatetimeIndex(target.index).tz is not None else pd.DatetimeIndex(target.index).to_period("M")
    factor = (target / old).reindex(old.index).fillna(1.0)
    per_row = factor.reindex(month).to_numpy()
    for c in [column] + list(also_scale or []):
        out[c] = frame[c].to_numpy() * per_row
    if recompute_net and {"elec_net_MW", "elec_total_MW", "elec_dg_MW"} <= set(out.columns):
        out["elec_net_MW"] = out["elec_total_MW"] + out["elec_dg_MW"]
    return out, factor


def fit_energy_peak(series: pd.Series, *, energy: float | None = None, peak: float | None = None,
                    constraints=("positive", "inverted")) -> pd.Series:
    """Affine rescale to hit both an energy (MWh) and a peak (MW) target,
    using `loads.calibrate.fit_load`. The hour of the original peak keeps the
    peak value; the minimum moves until the energy matches. Raises if the
    targets are infeasible under `constraints`."""
    from loads.calibrate import fit_load

    y, _err = fit_load(series.to_numpy(dtype=float), energy=energy, peak=peak, constraints=list(constraints))
    return pd.Series(np.asarray(y, dtype=float), index=series.index, name=series.name)

# Methodology

How `loads` produces a county load, what it promises, and what it does
not. Use this to explain results and to decide whether `loads` fits the
question. Summarized from the `loads` package docstring and source
(commit `a85f205`).

## Pipeline

```
ResStock 2018 (5 types) ─┐ × Census housing units ─────────► Residential
ComStock 2018 (14 types) ┘ × OpenEI floor area (no apts) ──► Commercial
NLR #97 county inventories, annual → average MW, flat ───────► Industry, Agriculture
transportation ──────────────────────────────────────────────► 0
                      Σ sectors (2018)  +  NSRDB 2018 weather  →  TSGAM fit
                      NSRDB weather for the target period      →  predict / sample
```

1. **Building-stock end uses.** NLR (formerly NREL) ResStock and ComStock
   2018 AMY end-use load profiles per county and building type (OEDI S3).
   End uses are collected into `baseload`, `cooling`, `heating` and DG
   (`Residential.COLLECT`, `Commercial.COLLECT`).
2. **Scaling.** Residential types are weighted by their stock unit counts
   and rescaled to Census 2018 housing units. Commercial is rescaled from
   stock floor area to OpenEI floor area, excluding apartments (counted in
   residential) and unmatched floor area.
3. **Industry and agriculture.** Annual county energy from NLR submission
   #97 (TBtu/yr → MW average). No hourly, daily or seasonal shape; not
   weather-driven; not checked against EIA.
4. **Training frame.** The 2018 sector loads plus the county's NSRDB 2018
   weather (county centroid) form the training set; total = Σ sectors,
   DG = −(|res DG| + |com DG|), net = total + DG.
5. **TSGAM.** `tsgam_estimator` fits, per target column, a time-series
   generalized additive model: Fourier terms for yearly/weekly/daily
   periodicity, spline responses to lagged weather (temperature and
   humidity for loads; direct and diffuse irradiance for DG), and an AR
   residual model. It is solved as a convex problem (CVXPY, CLARABEL).
6. **Prediction / sampling.** Applying the fitted model to another year's
   weather gives the expected load (`samples=0`); AR sampling gives
   realizations with realistic hour-to-hour variability.
7. **Calibration.** The package aims for 2018 residential/commercial energy
   and DG to sum, over each state, to EIA-861M retail sales and small-scale
   solar. In this commit the automated path (`Calibrate.load/solar`) is
   broken (see [footguns.md](footguns.md)); the example notebook
   `examples/county_total.py` in `loads` shows the intended monthly
   share-of-state calibration with `county_cf.csv` and EIA HS861m.

## Promises (from the package)

- complete hourly UTC coverage of the requested period;
- sector breakdown with consistent totals; DG never positive; net = total + DG;
- residential/commercial and DG respond to the period's weather;
- 2018 state totals agree with EIA (see caveat above);
- repeatable results via caching (`refresh=True` to rebuild).

## Not promised

- Industrial/agricultural shape or EIA agreement.
- Recalibration of predicted years (they inherit 2018 scaling, so load
  growth only enters through what the stock and inventory data encode; the
  `Estimator` docstring notes commercial floor-area growth is ignored).
- Coverage outside years with NSRDB weather; most exercise has been
  2018–2022 in WECC states. Future years need future weather that NSRDB
  does not have.
- Large loads (data centers, NERC "large loads"), EV/transportation load,
  behind-the-meter storage.
- Leading/trailing lag hours when sampling or predicting.

## Interpreting results

- **Expected vs realized.** Predictions are conditional means given
  weather; they are smoother than real load. Peaks from predictions are
  biased low relative to realized peaks. For peak planning use sample
  ensembles.
- **Weather drives differences between years**, not economics. Year-on-year
  changes in predicted load reflect weather plus whatever growth enters
  through scaling inputs.
- **County centroid weather.** Large counties (e.g. San Bernardino) span
  climates; one weather point is used.
- **Accuracy.** Upstream reports hold-out RMSE per medoid county in
  `loads/configs.csv` (0.04–0.67 GW for the six WECC medoids). For a
  specific county, measure it: `Estimator(county_st)` hold-out mode or
  `Total.test(...)`, then report RMSE/MAPE on the held-out rows.

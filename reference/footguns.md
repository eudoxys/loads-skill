# Footguns

Upstream rough edges in `eudoxys/loads` (commit `a85f205`), each traced to
the source, with the workaround. Items marked **[tested]** are reproduced
offline in `tests/test_loads_api.py`; if such a test starts failing, the
upstream behavior changed: update this file, do not just delete the test.

Do not silently "fix" these in `loads` from inside a workflow. Work around
them here and mention them to the user when they affect results; offer to
open an upstream issue at https://github.com/eudoxys/loads/issues.

## Modes and arguments

1. **`Total` has no `year`.** The `total.py` docstring example
   `Total("CA","Alameda",2020)` raises `TypeError` **[tested]**. Pass
   `date_range=` and `samples=`. → `loadskill.series` / `county_loads`.

2. **Default `samples=None` returns 2018 training data and ignores
   `date_range`.** Asking for 2021 without `samples` silently gives 2018.
   → always pass `samples`, or use `loadskill` modes and check
   `df.index.year`.

3. **CLI `-Y` is dropped for totals.** `Total.makeargs` keeps only
   annotated `__init__` args; `year` is not one **[tested]**. `loads print
   -S CA -C Alameda -Y 2020` prints 2018. → `python -m loadskill county`.

4. **Prediction frames hold one target.** `samples>=0` returns `X` + `Y`
   only. Sector columns, DG and net need separate calls. → `county_loads`.

5. **Industrial/agricultural cannot be predicted by default.** They are
   absent from `EXOGENOUS_VARIABLES` (`KeyError` without `X`), and are flat
   anyway. → copy the 2018 level (`county_loads(sectors=True)` does).

6. **Percentile ≠ realization.** `samples=n, percentile=p` gives the
   per-hour p-th percentile; its daily energy/peak are not those of any
   sample and overstate coincident peaks. → `mode="samples"` and compute
   statistics per sample.

7. **`samples=1` is random.** Upstream `aggregate()` uses it, so nodal
   aggregates differ run to run (TSGAM sampling is not seeded in
   `Total.TSGAM_CONFIG`: `random_state=None`). → use predictions for
   expected values; sample deliberately and record that you did.

8. **Lag-window NaN.** First/last 3 hours of every prediction are NaN.
   Downstream tools that reject NaN (players, solvers) fail or hold stale
   values. → `edges="fill"`/`"pad"`; `validate` reports edge NaN.

9. **Non-contiguous date ranges are bridged.** `Total` treats the whole
   `date_range` as one series; `[2019, 2021]` is fitted as if Dec 31 2019
   were followed by Jan 1 2021 (AR and lags cross the gap). →
   `loadskill.series` predicts each contiguous block separately.

10. **`Estimator` vs `Total`.** Different TSGAM configs (Estimator: log
    space, no AR, 4/4/6 harmonics, outlier model; Total: linear, AR 1–9,
    4/4/12 harmonics), different results, different location argument
    (`"Alameda CA"`). `Estimator` cannot model DG or net (log of ≤ 0).
    → pick one per study and record it.

## Calibration and energy

11. **`Calibrate(energy=...)` without `peak` raises** `AttributeError`
    (`None.keys()`) **[tested]**. → also pass `peak={}`.

12. **`Calibrate` energy fit is not proportional.** `fit_load` holds the
    value at the original peak hour and moves the minimum, reshaping the
    load **[tested]**. The module docstring describes P·E_new/E_old. →
    `loadskill.scale_to_energy` (proportional) or `fit_energy_peak`
    (explicit energy+peak).

13. **`Calibrate` string dates** use `pd.datetime`, removed from pandas. →
    pass `pd.Timestamp`. A window shorter than the frame raises a length
    mismatch (the fitted window is assigned to the whole column).

14. **`Calibrate.load` / `Calibrate.solar` always fail** with `TypeError`:
    they call `Residential(state, county, year)` positionally **[tested]**.
    Their cache check also never hits (`(state, year) in cls.CACHE` looks
    at the top-level keys). → compute state scalars yourself from EIA
    (`eia.HS861m`) and `loadskill.scale_*`.

15. **Predicted years are not recalibrated.** Only 2018 residential and
    commercial energy is tied to EIA (and only via the offline-built
    inputs). → for other years, calibrate to that year's EIA data and state
    which figures you matched.

16. **`Energy` needs a year pair.** An int `year` fails at `min(year)`
    **[tested]**. Its cache key ignores the county list (second call for a
    different county in the same state/period returns the first result).
    → `Energy(state, counties, [y0, y1], refresh=True)` or
    `loadskill.energy(frame, "MS")`.

## Locations and data

17. **Duplicate county names.** `fips` lists independent cities and
    counties with the same name (MD Baltimore, MO St. Louis, VA Fairfax,
    Franklin, Richmond, Roanoke). `loads` keys on `(state, county)` and
    cannot select one. → `resolve()` sets `County.ambiguous`; tell the user.

18. **Two location formats.** `Total`/sector classes: `state=, county=`.
    `Estimator`, `Cluster`, CSV maps: `"County ST"`.

19. **`DG` default source is relative to the working directory**
    (`"wecc/county_dg.csv.gz"`) **[tested]**, WECC only, and needs
    `date_range` for counties missing from the file. → pass an absolute
    path under `os.path.dirname(loads.__file__)`, or use `Total`'s DG.

20. **`Industry`/`Agriculture` `loadshape` must average 1.0** (values are
    `shape × average MW`), not total 1.0 as the docstring caveat says.

21. **Missing building types become zeros** (logged at DEBUG). A county
    with suspiciously low commercial load may lack ComStock coverage. →
    enable DEBUG logging for the `loads` modules when results look thin.

22. **`aggregate()` is WECC-only, nearest-node only, sample-based**, caches
    by year+column (changing targets needs `refresh=True`), and mishandles
    a list of years. → `nearest_nodes` + `allocate`.

## Environment

23. **Missing NSRDB credentials open a browser.** `weather` calls
    `webbrowser.open(SIGNUP)`; headless runs hang or fail obscurely. →
    `loadskill.configure()` checks first.

24. **Cache lives in site-packages by default** and `Total`/sector classes
    overwrite the global `Cache.CACHEDIR` when their own `CACHEDIR` is set.
    → set it once with `configure(cachedir=...)`.

25. **`Total.cache` keeps every fitted estimator in memory.** Sweeps over
    hundreds of counties grow without bound. → `configure(estimator_cache=
    False)` or `batch(clear_estimator_cache=True)`.

26. **Python 3.12 only** (`requires-python == 3.12.*`).

27. **`loads.dgen.SolarModel` prints** (`print(len(weather.index))`) to
    stdout, which corrupts stdout-JSON pipelines. → redirect stdout around
    that call, or avoid it (the default `DG` path does not use it).

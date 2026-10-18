# `loads` API, verified

Signatures below are copied from `eudoxys/loads` commit `a85f205` and
checked by `tests/test_loads_api.py`. "Fetches" lists the first-call
downloads (cached afterwards). "Returns" is what the constructed frame
contains. Read [footguns.md](footguns.md) for the traps each entry
mentions.

Public exports (`from loads import ...`): `Aggregator`, `Agriculture`,
`Calibrate`, `COMstock`, `Cluster`, `Commercial`, `DG`, `Energy`,
`Estimator`, `Floorarea`, `Industry`, `RESstock`, `Residential`, `Total`,
`Transportation`, `Units`, `main` (CLI). `Cast` lives in `loads.cast`;
`aggregate()` in `loads.aggregate`; `fit_load`, `integrate` in
`loads.calibrate`.

## Total

```python
Total(state: str, county: str, *, Y="elec_total_MW", X=None, dg=None,
      date_range: pd.DatetimeIndex = None, samples: int = None,
      percentile: float = 96, holdout=None, refresh=False)
```

The core model: sector sum for 2018 plus a TSGAM (time-series generalized
additive model, `tsgam_estimator`) fitted per `(state, county, X, Y)` and
used to predict or sample other periods from weather.

- `samples=None` → the 2018 training frame (all sectors, DG, total, net,
  weather). `date_range`, `X`, `percentile` are ignored. `Y` only selects
  `elec` vs `nonelec`.
- `samples=0` → deterministic prediction of `Y` over `date_range`.
- `samples=1` → one autoregressive sample.
- `samples>1, percentile=p` → per-hour p-th percentile across samples,
  returned in column `Y`.
- `samples>1, percentile=None` → `sample_0 … sample_{n-1}` columns.
- `date_range` must be a `pd.DatetimeIndex` (asserted) whenever `samples`
  is not `None`. Weather is fetched for every calendar year it touches.
- `X` defaults to `Total.EXOGENOUS_VARIABLES[Y]`:
  temperature + humidity for residential/commercial/total (elec and
  nonelec), direct + diffuse irradiance for `elec_dg_MW`. Any other `Y`
  needs `X`.
- `dg` and `holdout` are accepted and unused.
- Output index is converted to UTC and named `timestamp`. The first and
  last 3 rows of each predicted column are NaN.

Fetches: NSRDB weather (credentials), ResStock/ComStock (OEDI S3), Census
housing units, OpenEI floor area, NLR #97 industry/agriculture.

Class attributes worth knowing: `TRAINING_YEAR = 2018`, `TSGAM_CONFIG`
(harmonics `[4, 4, 12]` for year/week/day, 7-knot splines, lags −3…+3,
AR lags 1–9, CLARABEL), `TRANSFORMATIONS` (DG fitted as −DG), `cache`
(in-memory fitted estimators; set `Total.cache = None` to disable),
`CACHEDIR`, `INDUSTRY_LOADSHAPE`/`AGRICULTURE_LOADSHAPE` (None = flat).

Class methods:

- `Total.test(state, county, holdout, X=["temperature_degF"],
  Y="elec_total_MW", n_samples=0, refresh=False)` — fits on 2018 minus
  `holdout` rows and returns `X`, `Y` (actual), `predict` and optionally
  `sample[_n]`. Use for skill scores.
- `Total._clear_cache()` — drop fitted estimators (private but used by
  upstream sweeps).
- `Total.makeargs(**kw)` — keeps only kwargs annotated in `__init__`
  (CLI plumbing; drops `year`).

## Residential / Commercial

```python
Residential(state: str, county: str, *, collect=None, refresh=False)
Commercial(state: str, county: str, *, collect=None, refresh=False)
```

2018 hourly sector loads by category (see [data-model.md](data-model.md)).
`Residential` sums the five ResStock building types weighted by stock
units and rescales to Census 2018 housing units. `Commercial` sums the 14
ComStock types and rescales stock floor area to OpenEI floor area,
excluding apartments and unmatched area. `collect` overrides the end-use →
category map (`COLLECT`). There is no year argument.

## RESstock / COMstock

```python
RESstock(state: str, county: str = None, building_type: list[str] = None, refresh=False)
COMstock(state: str, county: str = None, building_type: list[str] = None, refresh=False)
```

Raw end-use data per building type: W per housing unit (`units` column) or
W/sf (`floor_area` column). Use for end-use studies (e.g. electrifying
heating: compare `gas_heating` and `elec_heating`).

## Industry / Agriculture

```python
Industry(state=None, county=None, loadshape=None, refresh=False)
Agriculture(state=None, county=None, loadshape=None, refresh=False)
```

Annual county energy from NLR submission #97 converted to average MW.

- No arguments → all counties (MultiIndex `state, county`); state only →
  that state's counties; state + county without `loadshape` → a one-column
  frame indexed by column name (`Industry("CA","Alameda").loc["elec_total_MW"]`).
- `loadshape` as a one-column DataFrame (any index) or a dict
  (`shape`, `start`, `end`, `freq`) → hourly frame = shape × average MW.
  The shape must **average** 1.0 to preserve annual energy (a vector of
  ones gives the flat load). The upstream docstring says "total 1.0"; that
  would divide the load by the number of hours.

## Units / Floorarea

```python
Units(state: str, county: str = None, year: int = None, refresh=False, aggregate=sum)  # -> float
Floorarea(state=None, county=None, year=None, refresh=False)
```

Census housing units (2020–2024 estimates) and OpenEI commercial floor area
by building type. Scaling inputs for the sector models.

## Estimator

```python
Estimator(county_st: str, years: list[int] = None, *, config: EstimatorConfig = None)
EstimatorConfig(verbose=False, debug=False, log=True, ar=False,
                outlier_regularizer=1e-4, outlier_threshold=5.0,
                solver="CLARABEL", harmonics=[4, 4, 6],
                sectors=["residential","commercial","industrial","agricultural"],
                enduse="elec_total_MW", weather=["temperature_degF","humidity_pc"],
                keep_actuals=True, holdout="5d")
```

Newer TSGAM front end, one string location (`"Alameda CA"`).

- `years=None` → hold-out test on 2018: columns weather, `actual`,
  `prediction`, `status` (`T` train / `H` held out). `holdout` is `"<N>h|d|w|m"`
  (every N-th hour/day/week/month) or a callable `frame -> index`.
- `years=[...]` → weather + `enduse` for those years, predicting every year
  from min to max then dropping the unrequested ones. 2018 rows are the
  actual training data when `keep_actuals`.
- Fits in log space by default (`log=True`), so it cannot represent zero
  or negative loads (no DG/net). AR off by default.
- Future years raise `EstimatorError` when NSRDB has no weather for them.

`Total` and `Estimator` use different TSGAM configurations and give
different predictions. Use one per study and say which.

## Calibrate

```python
Calibrate(load: pd.DataFrame, *, energy: dict[str, float] = None,
          peak: dict[str, float] = None, scale=1.0, offset=0.0,
          start=None, end=None)
```

For each column in `energy`/`peak`, `fit_load` affinely rescales the
column over `[start, end]` so its sum equals the energy and its value at
the original peak hour equals the peak; then the whole frame is
`* scale + offset`.

- Pass **both** dicts (`peak={}` if only energy): with one of them `None`
  it raises `AttributeError`.
- Pass `start`/`end` as `pd.Timestamp`; strings go through `pd.datetime`,
  which modern pandas lacks.
- Energy-only fitting keeps the peak and moves the minimum. It is not the
  proportional rule in the module docstring.
- The fit over `[start, end]` is assigned back to the whole column
  (`data[column] = fit`), so a window shorter than the frame raises a
  length mismatch. Leave `start`/`end` unset or span the full frame.
- `Calibrate.load(state, year)` and `Calibrate.solar(state, year)` (state
  scalars against EIA HS861m / Form 861m) both call
  `Residential(state, county, year)` / `Commercial(...)` with `year`
  positionally, which raises `TypeError`. Treat them as unavailable.

Use `loadskill.scale_to_energy` (proportional), `scale_monthly`, or
`fit_energy_peak` (wraps `fit_load`) instead.

## Energy

```python
Energy(state: str, counties: str | list[str] | None, year: int | tuple | list,
       month: int = None, *, groupby="1MS", datetime_format=None,
       progress=None, refresh=False)
```

Periodic MWh per county (`"County ST"` columns) from
`Total(..., samples=0)` predictions. Pass `year` as a 2-item list/tuple
(`[2018, 2022]`); a bare int fails at `min(year)` when building the cache
name. The cache name does not include the county list: calling it twice for
different counties in the same state and period returns the first result
unless `refresh=True`. Counties that fail become warnings, not zeros.

## DG

```python
DG(state: str, county: str, date_range=None, source="wecc/county_dg.csv.gz", on_missing="fillna")
```

County rooftop-solar series from a precompiled WECC CSV (`elec_dg_MW`).
`source` is relative to the **current directory**; pass
`os.path.join(os.path.dirname(loads.__file__), "wecc", "county_dg.csv.gz")`.
Counties absent from the file need `date_range` (otherwise it fails).
For non-WECC counties use `Total`'s `elec_dg_MW` (training or predicted).

## Aggregator / aggregate

```python
Aggregator(targets: list[str], start, end)          # zero panel, .add(target, frame)
aggregate(targets: dict[str, (lat, lon)], dt_range: int | list[int] | DatetimeIndex,
          column: str, refresh=False) -> (DataFrame, mapping)
```

`aggregate` maps every **WECC** county to its nearest target and sums
`Total(..., samples=1)` — a random AR sample, not a prediction — then caches
by year and column only (changing targets needs `refresh=True`). A list of
years is not handled correctly. Prefer `loadskill.nearest_nodes` +
`allocate` on frames you produced in a known mode.

## Cluster

```python
Cluster(counties: list[str], column: str, threshold=0.99, preprocess=None,
        progress=None, refresh=False)
cluster.kmeans(n_clusters: int)  # sets .medoids, .members, .closest, .centroids
```

SVD + energy-weighted k-means of county load shapes (rolled to local
standard time). `loads/clusters.csv` maps each WECC county to one of six
medoids; `loads/configs.csv` stores the best TSGAM settings per medoid.

## Cast

```python
from loads.cast import Cast
Cast(data: pd.DataFrame, year: int, weather=None)
```

Older weather-sensitivity back/forecast: shifts 2018 to align weekdays,
adds a leap day, fits logistic heating/cooling curves and applies the
weather difference. Superseded by `Total`/`Estimator`; use only when
reproducing older results.

## CLI

```
loads {print,plot} [-S STATE] [-C COUNTY] [-D DATASET] [-B BUILDING_TYPE]
      [-Y YEAR] [-o OUTPUT] [-f FORMAT] [-p PRECISION] [-w] [-d]
```

`-D total` (default) with `-Y` prints **2018 training data** (`Total` has
no `year`); `help`, `info`, `viewer`, `test` reference missing names or
files. Use `python -m loadskill` for year-aware output.

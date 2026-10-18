# Workflows

Recipes for composing `loads` into larger analyses. Each one: fetch in an
explicit mode, validate, then transform. All assume

```python
import pandas as pd
import loadskill as ls
ls.configure()          # cache folder + NSRDB credential check
```

and Python 3.12 with this repo installed (`uv sync`). Before any sweep, run
the recipe on one county and show the user the timing and a summary.

## 1. One county, one or more years

```python
c = ls.resolve("Maricopa County, AZ")
if c.ambiguous:
    print(f"warning: {c.county_st} is ambiguous in fips; loads cannot disambiguate")

df = ls.county_loads(c, [2019, 2020, 2021], sectors=True)   # total = Σ sectors
ls.validate(df, require_full_years=True).raise_if_failed()

print(ls.summary(df, "elec_total_MW"))
annual = ls.energy(df, "YS")                                   # MWh per year
peaks = ls.peaks(df, ["elec_total_MW", "elec_net_MW"], n=3)    # UTC times
local = ls.to_local(df, "America/Phoenix")                     # for reporting
ls.to_csv(df, "out/maricopa_2019_2021.csv.gz")
```

Choices to state in the write-up: `total="sum"` vs `"direct"`, `edges`,
and that 2018 rows (if any) are training data.

Only the total (no sectors) is cheaper: `county_loads(c, years)` fits two
models (total, DG) instead of four.

## 2. Sweep a state or interconnection

```python
places = ls.counties(state="NV")            # or system="WECC", region="CAISO"
res = ls.batch(places, ls.county_loads, 2020,
               progress=lambda name, n, k: print(f"{n}/{k} {name}", flush=True))
print(f"{len(res.frames)} ok, {len(res.errors)} failed")
for name, err in res.errors.items():
    print("FAILED", name, err)

panel = res.column("elec_net_MW")           # one column per county
state_total = panel.sum(axis=1, min_count=1)
cp = ls.coincident_peak(panel)              # contribution at the state peak
```

- `batch` collects failures instead of aborting, and clears fitted models
  between counties (`clear_estimator_cache=True`) to bound memory.
- Make long sweeps resumable: write each county to its own file and skip
  files that already exist and validate. `loads`' own cache makes repeated
  fetches fast, but your assembled frames are not cached.
- Run long sweeps in the background with output to a log file; first
  access per county can take minutes.

```python
import os
def county_file(c, year):
    path = f"out/{year}/{c.state}_{c.county.replace(' ', '_')}.csv.gz"
    if os.path.exists(path):
        return ls.read_csv(path)
    df = ls.county_loads(c, year)
    ls.validate(df).raise_if_failed()
    ls.to_csv(df, path)
    return df

res = ls.batch(places, county_file, 2020)
```

## 3. Counties → network nodes

```python
nodes = (pd.read_csv("https://github.com/eudoxys/wecc240/raw/refs/heads/main/wecc240/gis/wecc240.csv")
           .rename(columns={"LAT": "lat", "LON": "lon"})
           .drop_duplicates("GEOHASH").set_index("GEOHASH"))   # node id -> lat/lon

places = ls.counties(system="WECC")
mapping = ls.nearest_nodes(places, nodes, max_km=300)
unmapped = mapping[mapping.node.isna()]          # report these

res = ls.batch(places, ls.series, 2020)          # predicted elec_total_MW
county_series = {k: v["elec_total_MW"] for k, v in res.frames.items()}
nodal = ls.allocate(county_series, mapping, strict=False)
print("unallocated MWh:", ls.conservation_error(county_series, nodal))
ls.to_csv(nodal, "out/wecc240_2020_total.csv.gz",
          extra={"mapping": "nearest centroid", "max_km": 300})
```

- Nearest-centroid is a placeholder for a real county→bus allocation. When
  the user has one (e.g. from substation load shares), pass
  `{"County ST": {"bus_a": 0.7, "bus_b": 0.3}}` to `allocate`.
- Reading `nodes` from GitHub needs network; in a sandbox ask for the file.
- Report `conservation_error` and any unmapped or failed counties next to
  the nodal result.

## 4. Calibrate to known energy

Proportional, one target (e.g. a utility's reported annual sales for the
county):

```python
cal, k = ls.scale_to_energy(df, {"elec_total_MW": 12.3e6},          # MWh
                            start="2020-01-01", end="2020-12-31 23:00",
                            also_scale={"elec_total_MW": [c for c in df if c.startswith("elec_")
                                        and c not in ("elec_total_MW", "elec_dg_MW", "elec_net_MW")]})
ls.validate(cal).raise_if_failed()      # sector sum and net identity kept
```

Monthly, county share of EIA-861M state sales (needs the `eia` package
and network):

```python
from eia import HS861m
state = "NV"
months = pd.date_range("2020-01-01", "2020-12-01", freq="MS", tz="UTC")
state_mwh = pd.Series([HS861m(t.year, t.month).loc[state, "tot_energy_mwh"] for t in months],
                      index=months)
# share of each county in the modeled state total, per month
panel = res.column("elec_total_MW")                          # all counties in the state
share = panel.resample("MS").sum().div(panel.resample("MS").sum().sum(axis=1), axis=0)
cal = {name: ls.scale_monthly(frame, "elec_total_MW", state_mwh * share[name])[0]
       for name, frame in res.frames.items()}
```

Energy and peak together (affine; holds the peak hour, moves the minimum):

```python
y = ls.fit_energy_peak(df["elec_total_MW"], energy=12.3e6, peak=2450.0)
```

EIA retail sales are delivered energy net of behind-the-meter solar for
many customers; decide whether to match `elec_total_MW` or `elec_net_MW`
and say which. Industrial EIA sales are not comparable to the flat NLR
inventory without checking.

## 5. Uncertainty and peaks

```python
ens = ls.series(c, 2020, mode="samples", samples=50)
S = ens.filter(like="sample_")
peak_dist = S.max()                       # peak of each realization (MW)
energy_dist = S.sum()                     # annual MWh of each realization
band = S.quantile([0.1, 0.5, 0.9], axis=1).T   # hourly P10/P50/P90 (not trajectories)
print(peak_dist.describe(), energy_dist.describe())
```

`mode="percentile"` is cheaper but only gives a per-hour envelope; never
report its maximum as "the P95 peak".

## 6. Measure model skill for a county

```python
from loads import Estimator
ho = Estimator(c.county_st)                    # 2018, every 5th day held out
h = ho[ho.status == "H"]
rmse = ((h.prediction - h.actual) ** 2).mean() ** 0.5
mape = ((h.prediction - h.actual).abs() / h.actual).mean() * 100
```

`Estimator` uses its own configuration (log space, no AR). For the `Total`
model, use `Total.test(state, county, holdout_index, X=[...], Y=...)` with
a holdout index such as the last week of each month (the upstream
convention: `idx[idx.month != (idx + pd.Timedelta(days=7)).month]`).

## 7. Hand off to other tools

GridLAB-D player (kW, UTC):

```python
ls.to_player(df["elec_net_MW"], "alameda_net.player", scale=1e3)
```

PyPSA / production-cost models usually want naive timestamps and one column
per bus in MW:

```python
nodal.tz_convert("UTC").tz_localize(None).to_csv("loads-p_set.csv")
```

Tidy / database:

```python
ls.to_long(panel).to_parquet("county_loads.parquet")
```

Signal decomposition (e.g. `cvxgrp/cvx-sd-skill`): hourly series with
`delta = 3600` s; supply local *standard* time so the daily period is not
broken by DST:

```python
y = ls.to_local_standard(df, c.tzoffset)["elec_total_MW"].to_numpy()
```

## 8. End-use what-ifs with the raw stock data

`RESstock`/`COMstock` expose end uses per building type, e.g. gas space
heating that would be electrified:

```python
from loads import RESstock, Units
r = RESstock("CA", "Alameda", "RSD")          # W per housing unit, 2018
gas_heat_MW = r["gas_heating"] * Units("CA", "Alameda", 2018) / 1e6  # rough; all units as RSD
```

This scaling ignores the mix of building types; for a defensible estimate
weight each type by its stock `units` share the way `Residential` does, and
state the assumed heat-pump COP explicitly.

## 9. Report

When results go to a person, include: county list (and any ambiguous or
failed ones), years, mode (`prediction`/`sample`/`percentile`/training),
total convention (`direct`/`sum`), edge handling, calibration targets, and
the provenance sidecar. Quote the scope limits from
[methodology.md](methodology.md#not-promised) that matter for the question.

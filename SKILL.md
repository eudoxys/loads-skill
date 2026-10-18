---
name: loads
description: >-
  US county-level hourly electric load modeling with eudoxys/loads: build
  residential, commercial, industrial and agricultural load, distributed
  (rooftop solar) generation and net load for a county and year from
  ResStock/ComStock, Census, OpenEI, NLR and NSRDB weather data; predict or
  sample other years with the TSGAM weather model; validate, summarize,
  calibrate to known energy, aggregate counties onto network nodes, and
  export to downstream tools. Use when a task needs a realistic load shape,
  load forecast/backcast by weather, sector breakdown, net load, or nodal
  load profiles for US counties (best exercised for WECC, 2018-2022), or
  when existing code calls `loads.Total`, `Residential`, `Commercial`,
  `Estimator`, `Calibrate` or `aggregate`.
allowed-tools: Read, Write, Edit, Bash(uv run **), Bash(python -m loadskill **)
---

`loads` turns public building-stock, census, inventory and weather data into
hourly county load, in MW, by sector, driven by the county's actual weather.
This skill puts it to work inside larger workflows. Use **`loads`** for every
number; use **`loadskill`** (this repo) to resolve places, call `loads` in an
explicit mode, check what came back against the package contract, summarize
it, calibrate or aggregate it, and hand it on with provenance.

`loadskill` never changes the model. If a result looks wrong, the cause is
upstream data or `loads` itself; say so rather than patching numbers.

Locate an installed copy with
`python -c "import loads, loadskill; print(loads.__file__, loadskill.__file__)"`.
The `loads` source is short and well documented; read the module before
relying on behavior this skill does not cover.

## Before the first call

Do these once, at workflow start. Skipping them fails late or never returns.

1. **Python 3.12.** `loads` pins `==3.12.*`. In this repo: `uv sync`.
2. **NSRDB credentials.** Every `Total` call fetches NSRDB weather. Without
   `~/.nsrdb/credentials.json` (`{"<email>": "<api_key>"}`) the `weather`
   package tries to open a sign-up page in a browser, which hangs headless
   agents. Only the user can register (https://developer.nlr.gov/signup/);
   never invent a key.
3. **Cache folder.** Upstream caches inside site-packages by default.
   `loadskill.configure()` points it at `$LOADS_CACHEDIR` or
   `~/.cache/eudoxys` and raises early if credentials are missing.
4. **Budget time.** First access to a county downloads several sources and
   fits a TSGAM model per target column: minutes per county, hours for a
   state or interconnection sweep. Results are cached afterwards. Test on one
   county (Alameda CA is the upstream convention) before sweeping.

```bash
uv run python -m loadskill env      # cachedir + credentials status (JSON)
```

## The loop

Resolve -> fetch in an explicit mode -> validate -> use -> export with provenance.

```python
import loadskill as ls

ls.configure()                                   # cache dir + credential check
c = ls.resolve("Alameda County, CA")             # -> County(state="CA", county="Alameda", ...)

df = ls.county_loads(c, 2020, sectors=True)      # total, sectors, DG, net + weather
rep = ls.validate(df, require_full_years=True)   # the loads contract, checked
rep.raise_if_failed()

facts = ls.summary(df, "elec_net_MW")            # energy MWh, peak, load factor
monthly = ls.energy(df, "MS")                    # *_MWh per month
ls.to_csv(df, "out/alameda_2020.csv.gz")         # + .meta.json provenance sidecar
```

Shell equivalent: `uv run python -m loadskill county "Alameda CA" 2020
--sectors -o out/alameda_2020.csv.gz` prints a JSON report including
validation; exit code 2 means the frame failed validation.

## Pick the mode deliberately

`loads.Total(state, county, ...)` changes behavior with `samples`. Most
mistakes with this package are a wrong mode. `loadskill.series` names them:

| Need                                  | `loadskill`                                   | `loads.Total`                          | Output columns                     |
|---------------------------------------|-----------------------------------------------|----------------------------------------|------------------------------------|
| Reference ("actual") 2018 load        | `training(c)`                                 | `Total(st, co)`                        | weather + every sector, DG, total, net |
| Expected load for a year (weather-driven) | `series(c, 2021)`                         | `Total(..., date_range=idx, samples=0)` | X weather + one target            |
| One plausible realization             | `series(c, 2021, mode="sample")`              | `samples=1`                            | X + target (random AR draw)        |
| A high/low planning quantile          | `series(c, 2021, mode="percentile", samples=200, percentile=95)` | `samples=200, percentile=95` | X + target at that percentile (per hour, not a coherent trajectory) |
| An ensemble for uncertainty           | `series(c, 2021, mode="samples", samples=50)` | `samples=50, percentile=None`          | X + `sample_0..49`                 |

Facts that follow from the source:

- `samples=None` (the default) returns 2018 training data and **ignores
  `date_range`**. `Total("CA", "Alameda", 2020)` from the upstream docstring
  raises `TypeError` (there is no `year` argument) and `loads print -Y 2020`
  silently prints 2018.
- Predict/sample modes return **only** the exogenous weather columns and the
  one target `Y`. For total + DG + net + sectors in a year other than 2018,
  call once per target; `county_loads` does that and assembles them.
- Predictable targets: `elec_total_MW`, `elec_residential_MW`,
  `elec_commercial_MW`, `elec_dg_MW` and their `nonelec_` analogues.
  Industrial and agricultural are flat at the 2018 level (no shape, no
  weather response); transportation is zero.
- The first 3 and last 3 hours of every predicted series are NaN (lag
  window). `edges="fill"` (default) copies the nearest hour, `"pad"` widens
  the request and trims, `"nan"` keeps them.
- A percentile series is the per-hour quantile across samples; its energy
  and peak are not the energy or peak of any realization. For peak or
  energy distributions, use `mode="samples"` and compute the statistic per
  sample.

## Contract to check, not assume

`loads` documents its invariants and that some do not always hold.
`ls.validate(df)` checks them on the frame you got:

- hourly, tz-aware UTC `timestamp` index, no gaps or duplicates; 8760/8784
  rows per full year;
- `elec_dg_MW <= 0` (DG is a negative load);
- `elec_net_MW == elec_total_MW + elec_dg_MW`;
- `elec_total_MW == Σ elec_{sector}_MW` on `Total` frames, and
  `== baseload + cooling + heating` on sector-model frames;
- no NaN except in the lag window; plausible weather ranges.

Report validation failures to the user with the frame's provenance
(`df.attrs["loadskill"]`); do not drop columns or rows to make a check pass.

## Workflows

Read [workflows.md](reference/workflows.md) for complete recipes:

- one county, one or more years, with sector breakdown and net load;
- state or interconnection sweeps with `batch` (errors collected, memory
  bounded) and county panels;
- county -> bus/zone aggregation with `nearest_nodes` + `allocate`
  (fractional splits supported, energy conservation reported);
- calibrating to EIA-861M or utility energy (`scale_to_energy`,
  `scale_monthly`) and to energy + peak (`fit_energy_peak`);
- uncertainty bands and peak distributions from sample ensembles;
- hold-out skill testing (`Estimator(county_st)`, `Total.test`);
- handing loads to GridLAB-D players, PyPSA/production-cost CSVs, or
  cvx-sd signal decomposition.

## Footguns

These fail silently. The full list with source references is in
[footguns.md](reference/footguns.md).

- **Wrong mode.** Training data returned where a year was intended (see
  above). Check `df.index.year.unique()` and `df.attrs["loadskill"]["mode"]`.
- **Ambiguous county names.** `fips` has Baltimore city and Baltimore
  County, St. Louis city and County, several Virginia pairs. `loads` keys on
  `(state, county)` only and cannot tell them apart; `resolve()` sets
  `County.ambiguous`. Tell the user.
- **UTC everywhere.** Months, days and peaks from raw output are UTC. Convert
  (`to_local`, `to_local_standard`) before reporting local calendar
  quantities.
- **`direct` vs `sum` totals.** `Total`'s own `elec_total_MW` model and the
  sum of separately predicted sector models differ by a few percent. Pick
  one per study (`county_loads(total=...)`).
- **`Calibrate` is not proportional** and has argument bugs; prefer
  `loadskill.calibrate`. See [api.md](reference/api.md#calibrate).
- **Two location formats.** `Total`, `Residential`, ... take
  `state="CA", county="Alameda"`; `Estimator`, `Cluster`, `clusters.csv`
  take `"Alameda CA"`. `County.kwargs` and `County.county_st` give both.
- **Scope.** Calibrated to EIA only for the 2018 residential/commercial
  totals; other years inherit 2018 calibration. Large loads (data centers)
  and EV/transportation load are not modeled. Say so when results feed
  decisions.

## Reference

- [data-model.md](reference/data-model.md) — columns, units, sign
  conventions, index, sectors, end-use collection, building-type codes.
- [api.md](reference/api.md) — every public `loads` class: verified
  signature, what it fetches, what it returns, caveats.
- [methodology.md](reference/methodology.md) — how the estimate is built
  (stock models, scaling, TSGAM, DG, calibration) and what is not promised.
- [workflows.md](reference/workflows.md) — end-to-end recipes for composing
  `loads` into larger analyses.
- [footguns.md](reference/footguns.md) — known upstream rough edges, each
  traced to source, with the workaround.
- [operations.md](reference/operations.md) — data sources, credentials,
  caching, runtime, memory, offline behavior, CI.

## Worked examples

- [`examples/county_year.py`](examples/county_year.py) — one county, one
  year: fetch, validate, summarize, export (needs data access).
- [`examples/nodal_profiles.py`](examples/nodal_profiles.py) — sweep a
  state, map counties to buses, check conservation, write node CSVs.
- [`examples/uncertainty.py`](examples/uncertainty.py) — sample ensemble ->
  peak distribution and P10/P50/P90 hourly band.
- [`examples/offline_demo.py`](examples/offline_demo.py) — the helper
  pipeline on a synthetic `Total`-shaped frame; runs with no network.

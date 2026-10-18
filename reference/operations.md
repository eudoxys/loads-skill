# Operations

Running `loads` reliably inside automated workflows: installation, data
access, credentials, caching, runtime and memory.

## Install

```bash
uv sync                      # Python 3.12 venv with loads, loadskill, pytest
uv run python -m pytest -q   # offline tests (no network needed)
```

`loads` and its siblings install from GitHub (`eudoxys/cache`, `fips`,
`weather`, `eia`, `geohash`, and `nimish/estimator` for TSGAM, plus pvlib).
Without uv: `python3.12 -m venv .venv && . .venv/bin/activate &&
pip install -e .`.

## Data sources fetched at first use

| Source | Used by | Host |
|---|---|---|
| ResStock 2018 county end-use profiles | `RESstock` → `Residential` | `oedi-data-lake.s3.amazonaws.com` |
| ComStock 2018 county end-use profiles | `COMstock` → `Commercial` | `oedi-data-lake.s3.amazonaws.com` |
| Census housing-unit estimates | `Units` | `www2.census.gov` |
| OpenEI commercial floor area (#906) | `Floorarea` | `data.openei.org` |
| NLR county industry/agriculture (#97) | `Industry`, `Agriculture` | `data.nlr.gov` |
| NSRDB PSM4 hourly weather (via pvlib) | `weather.Weather` → every `Total` | NSRDB API (key) |
| EIA-861M sales / small-scale solar | `eia.HS861m`, `Form861m` | `www.eia.gov` |
| WECC240 node GIS (optional) | your aggregation | `github.com/eudoxys/wecc240` |

Bundled (offline): `fips` county/state metadata, `loads/clusters.csv`,
`loads/configs.csv`, `loads/wecc/*` (precompiled WECC county DG and
energy factors), `loads/caiso`, `loads/isone` reference data.

In network-restricted sandboxes these hosts are often blocked; the
symptom is `URLError` / `403 Forbidden` from the first constructor. In
that case `loadskill` still works on frames the user provides (CSV from
an earlier run): `read_csv`, `validate`, `summary`, `allocate`, etc. Say
what is blocked and ask for the files rather than retrying.

## NSRDB credentials

`~/.nsrdb/credentials.json` containing `{"<email>": "<api_key>"}`. The
user registers at https://developer.nlr.gov/signup/. CI (`loads`'
`validate.yaml`) writes it from a `NSRDB_CREDENTIALS` secret; do the same
in your CI. `loadskill.check_credentials()` returns whether the file is
usable; `configure()` raises if not.

## Cache

`cache.Cache` stores everything under `CACHEDIR/loads/<version>/<state>/
<county>/...` (and `CACHEDIR/weather/...` etc.). Defaults to a `.cache`
folder inside the installed `cache` package. Set it once:

```python
ls.configure(cachedir="/data/eudoxys-cache")   # or env LOADS_CACHEDIR
```

- Cache files are CSV(.gz) keyed by state/county/source; delete a county
  folder to force a rebuild of just that county, or pass `refresh=True`.
- `cache` has backup/restore (`cache backup -f file.tar.gz`, `cache
  restore -f file.tar.gz`) for moving a warmed cache between machines; a
  warmed cache is the practical way to run `loads` where the data hosts are
  unreachable.
- Cache writes are not atomic. Do not run two processes on the same county
  at once.

## Runtime and memory

- First call for a county: several downloads plus a TSGAM fit per target
  column (CVXPY + CLARABEL). Expect minutes. Cached reruns: seconds plus
  the fit (fitted models are cached only in memory, per process).
- `county_loads(sectors=True)` fits four models (total, residential,
  commercial, DG); without sectors, two.
- Sampling cost scales with `samples`.
- A full WECC sweep (≈400 counties) takes hours. Run it in the background,
  log progress, write per-county outputs so it can resume.
- `Total.cache` holds fitted estimators; disable or clear it in sweeps.
- Parallelism: separate processes per state are safe if they share no
  county; the cache layout is per county.

## Logging

`loads` modules log via `logging.getLogger(__file__)`. For cache hits and
missing building types:

```python
import logging
logging.basicConfig(level=logging.INFO)
logging.getLogger().setLevel(logging.DEBUG)   # very chatty
```

## Versions and provenance

`loadskill` records the installed `loads` version and commit in
`frame.attrs["loadskill"]["loads_version"]` and in every `.meta.json`
sidecar. Pin `loads` to a commit for reproducible studies:

```toml
dependencies = ["loads @ git+https://github.com/eudoxys/loads@<commit>"]
```

After upgrading `loads`, run `uv run python -m pytest -q`;
`tests/test_loads_api.py` flags upstream changes this skill documents.

# Loads Skill

**US county electric load modeling for agents** — an agent skill and a thin
helper library that let a capable language model use
[`eudoxys/loads`](https://github.com/eudoxys/loads) inside larger
workflows: building hourly county loads by sector, net of rooftop solar,
for a given year's weather; checking them; summarizing, calibrating and
aggregating them; and handing them to the next tool with provenance.

> ⚠️ **Work in progress.** `loads` itself is alpha. The skill documents its
> behavior as of commit `a85f205` and guards that description with tests;
> interfaces may change.

## What this is

Two things, meant to work together (the layout follows
[cvxgrp/cvx-sd-skill](https://github.com/cvxgrp/cvx-sd-skill)):

1. **An agent skill** ([`SKILL.md`](SKILL.md) + [`reference/`](reference/))
   that teaches a model how `loads` works, which mode answers which
   question, what the package promises and where it does not deliver, and
   how to compose it with calibration, aggregation and downstream models.

2. **A small, tested Python package** (`loadskill`) that makes the safe
   path the easy one: place-name resolution, explicit `Total` modes,
   contract validation, summaries, proportional calibration, county→node
   allocation, and CSV/player export with a provenance sidecar. It never
   changes the model; every number comes from `loads`.

The design bet is that a capable model can write pandas and reason about
loads, but does not know this package's conventions and traps: `Total`
returns 2018 training data unless you ask otherwise, prediction frames hold
one target, the edges are NaN, calibration is not proportional, one CLI
flag is silently ignored, county names collide. The skill makes those
explicit and the library makes them checkable.

## Quick taste

```python
import loadskill as ls

ls.configure()                                  # cache folder + NSRDB credential check
c = ls.resolve("Alameda County, CA")

df = ls.county_loads(c, 2020, sectors=True)     # sectors, total, DG, net, weather (MW, hourly UTC)
ls.validate(df, require_full_years=True).raise_if_failed()

ls.summary(df, "elec_net_MW")                   # energy, peak, load factor
ls.energy(df, "MS")                             # monthly MWh
ls.to_csv(df, "out/alameda_2020.csv.gz")        # + .meta.json provenance
```

From a shell (JSON on stdout; exit 2 on validation failure):

```bash
uv run python -m loadskill county "Alameda CA" 2020 --sectors -o out/alameda_2020.csv.gz
uv run python -m loadskill series "Alameda CA" 2021 --mode percentile --samples 200 --percentile 95 -o p95.csv
uv run python -m loadskill summarize out/alameda_2020.csv.gz --column elec_net_MW
```

## Potential agentic use

Some requests this skill is built for:

- *"Give me hourly 2021 load for every county in Nevada, by sector, and
  tell me which counties drive the state peak."* → `counties` + `batch` +
  `coincident_peak`, with failures and ambiguous names reported.
- *"Build bus-level load profiles for our 240-bus WECC model for 2019–2022,
  matched to EIA monthly sales."* → `series` per county, `nearest_nodes` /
  `allocate`, `scale_monthly`, conservation check, per-node CSVs.
- *"How much could a hot summer raise Maricopa's peak?"* → sample ensemble,
  peak distribution, not the percentile envelope.
- *"Feed Alameda's net load into this GridLAB-D feeder model."* →
  `to_player` in kW with provenance.
- *"Is this load-model code right?"* → read it against
  [footguns.md](reference/footguns.md) (wrong mode, ignored year, bridged
  gaps, non-proportional calibration).

## Installing the skill

Clone into a skills folder your agent reads (for Claude Code,
`~/.claude/skills/` or a project's `.claude/skills/`), then install the
environment:

```bash
git clone https://github.com/eudoxys/loads-skill ~/.claude/skills/loads-skill
cd ~/.claude/skills/loads-skill && uv sync
```

Requirements: Python 3.12 (pinned by `loads`), network access to the data
sources listed in [operations.md](reference/operations.md), and NSRDB API
credentials in `~/.nsrdb/credentials.json`
(register at https://developer.nlr.gov/signup/).

## Layout

```
SKILL.md                 agent entry point: setup, the loop, modes, contract, footguns
reference/
  data-model.md          columns, units, signs, index, building types, locations
  api.md                 every public loads class, verified signatures and behavior
  methodology.md         how the estimate is built; what is and is not promised
  workflows.md           recipes: sweeps, nodal aggregation, calibration, uncertainty, hand-off
  footguns.md            upstream rough edges traced to source, with workarounds
  operations.md          data sources, credentials, cache, runtime, provenance
src/loadskill/           helper package (fetch, validate, summarize, calibrate, aggregate, export, cli)
examples/                offline demo + county, nodal and uncertainty scripts
tests/                   offline tests, upstream-API guards, opt-in network tests
```

## Tests

```bash
uv run python -m pytest -q             # offline: helpers + checks of documented loads behavior
uv run python -m pytest -m network -q  # end-to-end on Alameda CA (data access + credentials)
uv run python examples/offline_demo.py
```

`tests/test_loads_api.py` reproduces, without network, the upstream
behaviors the skill warns about. When `loads` changes, those tests say
which parts of the skill to update.

## License

MIT, matching `eudoxys/loads`. See [LICENSE](LICENSE).

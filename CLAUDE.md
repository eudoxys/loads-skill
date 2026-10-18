# Working in this repository

This repo holds an agent skill (`SKILL.md` + `reference/`) for the
[`eudoxys/loads`](https://github.com/eudoxys/loads) package and a thin helper
package, `loadskill` (`src/loadskill/`). The project is `loads-skill`; the
import is `loadskill`. `loads` is a dependency, not vendored.

## Running tests

```bash
uv sync
uv run python -m pytest -q              # offline (default deselects network tests)
uv run python -m pytest -m network -q   # needs data access + ~/.nsrdb/credentials.json
```

## The cardinal discipline: verify against `loads`, don't recall

Every statement about `loads` in `SKILL.md` and `reference/` must be true of
the pinned upstream source.

- Read the `loads` module before documenting it
  (`python -c "import loads; print(loads.__file__)"`).
- Copy signatures from source; `tests/test_loads_api.py` checks the ones
  that matter. If you document a new upstream behavior that can be
  reproduced offline, add a test there.
- Run every snippet you add. Snippets that need network go in `examples/`
  or tests marked `network`; mark them as such in the prose.
- Note the upstream commit when the description changes
  (currently `a85f205`).

## Package conventions

- `loadskill` never alters model output beyond documented, opt-in
  post-processing (edge fill, DG clip to ≤ 0, scaling the user asked for).
  Every such step is recorded in `frame.attrs["loadskill"]`.
- `loads` imports inside `fetch` are lazy so validation, summaries and
  aggregation work offline on saved frames.
- Frames keep `loads` conventions: hourly tz-aware UTC `timestamp` index,
  `*_MW` columns, DG ≤ 0, net = total + DG.
- Locations go through `resolve()`; never hand-build `"County ST"` strings.

## Upstream issues

Do not patch `loads` from here. Document the behavior in
`reference/footguns.md` with a source reference and workaround, add an
offline reproduction to `tests/test_loads_api.py` when possible, and raise
it at https://github.com/eudoxys/loads/issues.

## Documentation state

Keep workflow and routing in concise `SKILL.md`; put details in one
canonical reference file each. `SKILL.md`'s Reference list is the index.

## License

MIT (same as `loads`).

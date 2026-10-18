"""Guard the facts the skill documents about `loads`.

These tests import `loads` but touch no network. If one fails after a
`loads` update, update SKILL.md / reference/ and `loadskill.schema` to match
the new upstream behavior; do not just relax the test.
"""

import inspect

import loads
import pytest

from loadskill import schema


def params(fn):
    return inspect.signature(fn).parameters


def test_total_signature():
    p = params(loads.Total.__init__)
    assert list(p)[:3] == ["self", "state", "county"]
    for name in ("Y", "X", "date_range", "samples", "percentile", "refresh"):
        assert p[name].kind is inspect.Parameter.KEYWORD_ONLY
    assert "year" not in p  # docstring example Total("CA","Alameda",2020) is wrong
    assert p["samples"].default is None and p["percentile"].default == 96


def test_cli_year_is_dropped_for_total():
    # makeargs keeps only annotated __init__ args; Total has no `year`
    assert "year" not in loads.Total.makeargs(state="CA", county="Alameda", year=2020)


def test_total_constants_match_schema():
    assert loads.Total.TRAINING_YEAR == schema.TRAINING_YEAR
    assert {k: tuple(v) for k, v in loads.Total.EXOGENOUS_VARIABLES.items()} == schema.PREDICTABLE_TARGETS
    lags = [l for c in loads.Total.TSGAM_CONFIG.exog_config for l in getattr(c, "lags", [])]
    assert tuple(sorted(set(lags))) == schema.TSGAM_LAGS


def test_building_types_match_schema():
    assert set(loads.RESstock.BUILDING_TYPES) == set(schema.RESIDENTIAL_BUILDING_TYPES)
    assert set(loads.COMstock.BUILDING_TYPES) == set(schema.COMMERCIAL_BUILDING_TYPES)


def test_sector_models_keyword_only_after_county():
    for cls in (loads.Residential, loads.Commercial):
        p = params(cls.__init__)
        assert p["refresh"].kind is inspect.Parameter.KEYWORD_ONLY
        assert "year" not in p  # so Calibrate.load(...) passing year positionally fails


def test_calibrate_requires_peak_dict():
    import pandas as pd
    idx = pd.date_range("2018-01-01", periods=48, freq="1h", tz="UTC", name="timestamp")
    df = pd.DataFrame({"elec_total_MW": range(1, 49)}, index=idx, dtype=float)
    with pytest.raises(AttributeError):
        loads.Calibrate(df, energy={"elec_total_MW": 2000.0})  # peak=None -> None.keys()
    out = loads.Calibrate(df, energy={"elec_total_MW": 2000.0}, peak={})
    assert abs(out["elec_total_MW"].sum() - 2000.0) < 1e-2
    assert abs(out["elec_total_MW"].max() - 48.0) < 1e-9  # peak held, not proportional


def test_estimator_uses_county_st():
    p = params(loads.Estimator.__init__)
    assert list(p)[1] == "county_st"
    from loads.estimator import EstimatorConfig
    assert EstimatorConfig().log is True and EstimatorConfig().holdout == "5d"


def test_energy_needs_year_sequence():
    p = params(loads.Energy.__init__)
    assert list(p)[1:4] == ["state", "counties", "year"]


# --- documented failures that can be reproduced without network -------------

def test_total_positional_year_raises():
    with pytest.raises(TypeError):
        loads.Total("CA", "Alameda", 2020)


def test_calibrate_load_passes_year_positionally(tmp_path, monkeypatch):
    from cache import Cache
    monkeypatch.setattr(Cache, "CACHEDIR", str(tmp_path))
    with pytest.raises(TypeError):
        loads.Calibrate.load("NV", 2019, refresh=True)


def test_energy_int_year_fails(tmp_path, monkeypatch):
    from cache import Cache
    monkeypatch.setattr(Cache, "CACHEDIR", str(tmp_path))
    with pytest.raises(TypeError):
        loads.Energy("NV", "Esmeralda", 2019)


def test_dg_default_source_is_cwd_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError):
        loads.DG("CA", "Alameda")

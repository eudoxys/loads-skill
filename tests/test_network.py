"""End-to-end checks against real `loads` data (Alameda CA, the upstream
convention). Slow on first run: they download ResStock/ComStock, Census,
OpenEI, NLR and NSRDB data and fit TSGAM models.

    uv run python -m pytest -m network -q
"""

import pytest

from loadskill import configure, county_loads, series, summary, training, validate

pytestmark = pytest.mark.network


@pytest.fixture(scope="module", autouse=True)
def env():
    return configure()


def test_training_frame_contract():
    df = training("Alameda CA")
    assert len(df) == 8760
    rep = validate(df, require_full_years=True)
    assert rep.ok, str(rep)


def test_predict_2020():
    df = series("Alameda CA", 2020)
    assert len(df) == 8784 and df["elec_total_MW"].notna().all()
    assert summary(df)["peak_MW"] > 0


def test_county_loads_2020_sectors():
    df = county_loads("Alameda CA", 2020, sectors=True)
    assert validate(df, require_full_years=True).ok

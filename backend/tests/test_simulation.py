import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.aggregate import build_response
from app.defaults import (
    DEFAULT_DEMAND,
    DEFAULT_GENERATION,
    PRESETS,
)
from app.simulation import DAYS_PER_YEAR, run_simulation


def test_run_simulation_length():
    periods = run_simulation(DEFAULT_GENERATION, DEFAULT_DEMAND)
    assert len(periods) == DAYS_PER_YEAR * 2


def test_no_negative_supply_or_demand():
    periods = run_simulation(DEFAULT_GENERATION, DEFAULT_DEMAND)
    for p in periods:
        assert p.demand_mwh >= 0
        for v in p.supply_mwh.values():
            assert v >= -1e-6
        assert p.unmet_demand_mwh >= -1e-6


def test_default_mix_meets_demand():
    # The default (current UK-like) mix has plenty of gas to cover any gap,
    # so it should never be short.
    response = build_response(DEFAULT_GENERATION, DEFAULT_DEMAND)
    assert response["headline"]["reliability_ok"] is True
    assert response["headline"]["total_unmet_demand_mwh"] < 1.0


def test_solar_zero_at_night():
    periods = run_simulation(DEFAULT_GENERATION, DEFAULT_DEMAND)
    night_periods = [p for p in periods if p.period == "night"]
    for p in night_periods:
        assert p.supply_mwh.get("solar_field", 0.0) == 0.0
        assert p.supply_mwh.get("solar_roof", 0.0) == 0.0


def test_nuclear_flat_across_periods():
    periods = run_simulation(DEFAULT_GENERATION, DEFAULT_DEMAND)
    nuclear_values = {round(p.supply_mwh.get("nuclear", 0.0), 3) for p in periods}
    assert len(nuclear_values) == 1


def test_generation_shares_sum_to_100():
    response = build_response(DEFAULT_GENERATION, DEFAULT_DEMAND)
    total_share = sum(response["headline"]["generation_share_pct"].values())
    assert abs(total_share - 100.0) < 0.5


def test_headline_cost_positive():
    response = build_response(DEFAULT_GENERATION, DEFAULT_DEMAND)
    assert response["headline"]["cost_per_mwh"] > 0
    assert response["headline"]["total_cost_gbp"] > 0


def test_zero_capacity_everything_gives_full_unmet_demand():
    zero_gen = DEFAULT_GENERATION.model_copy(deep=True)
    for field_name in zero_gen.model_fields:
        if field_name.endswith("_gw"):
            setattr(zero_gen, field_name, 0.0)
    response = build_response(zero_gen, DEFAULT_DEMAND)
    assert response["headline"]["reliability_ok"] is False
    assert response["headline"]["total_unmet_demand_mwh"] > 0


def test_presets_run_without_error():
    for preset in PRESETS.values():
        response = build_response(preset["generation"], DEFAULT_DEMAND)
        assert len(response["daily"]) == DAYS_PER_YEAR
        assert response["headline"]["total_demand_mwh"] > 0


def test_curtailment_only_when_surplus():
    # Renewables-only heavy preset should show some curtailment somewhere in the year
    response = build_response(PRESETS["renewables_only"]["generation"], DEFAULT_DEMAND)
    assert response["headline"]["total_curtailment_mwh"] >= 0


def test_dash_for_gas_preset_hits_roughly_80_percent_gas():
    response = build_response(PRESETS["dash_for_gas"]["generation"], DEFAULT_DEMAND)
    gas_share = response["headline"]["generation_share_pct"]["gas"]
    assert 78.0 <= gas_share <= 82.0
    assert response["headline"]["reliability_ok"] is True


def test_geothermal_flat_across_periods():
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    gen.geothermal_gw = 3.0
    periods = run_simulation(gen, DEFAULT_DEMAND)
    geothermal_values = {round(p.supply_mwh.get("geothermal", 0.0), 3) for p in periods}
    assert len(geothermal_values) == 1
    assert next(iter(geothermal_values)) > 0


def test_tidal_is_deterministic_and_bounded():
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    gen.tidal_gw = 2.0
    periods_a = run_simulation(gen, DEFAULT_DEMAND)
    periods_b = run_simulation(gen, DEFAULT_DEMAND)
    tidal_a = [p.supply_mwh.get("tidal", 0.0) for p in periods_a]
    tidal_b = [p.supply_mwh.get("tidal", 0.0) for p in periods_b]
    assert tidal_a == tidal_b
    max_possible = gen.tidal_gw * 1000 * 12.0  # 100% capacity factor ceiling
    assert all(0 <= v <= max_possible for v in tidal_a)
    assert any(v > 0 for v in tidal_a)


def test_morocco_link_is_dispatchable_like_interconnector():
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    for field_name in gen.model_fields:
        if field_name.endswith("_gw"):
            setattr(gen, field_name, 0.0)
    gen.morocco_link_gw = 5.0
    gen.morocco_link_price = 10  # cheapest possible so it's guaranteed to be dispatched
    response = build_response(gen, DEFAULT_DEMAND)
    assert response["headline"]["generation_share_pct"]["morocco_link"] > 0


def test_hydro_is_deterministic_seasonal_and_bounded():
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    gen.hydro_gw = 3.0
    periods_a = run_simulation(gen, DEFAULT_DEMAND)
    periods_b = run_simulation(gen, DEFAULT_DEMAND)
    hydro_a = [p.supply_mwh.get("hydro", 0.0) for p in periods_a]
    hydro_b = [p.supply_mwh.get("hydro", 0.0) for p in periods_b]
    assert hydro_a == hydro_b
    max_possible = gen.hydro_gw * 1000 * 12.0
    assert all(0 <= v <= max_possible for v in hydro_a)
    assert any(v > 0 for v in hydro_a)
    # Winter (day 0) should be wetter/higher output than midsummer (day ~172).
    assert hydro_a[0] > hydro_a[172 * 2]


def test_nuclear_slider_allows_up_to_100gw():
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    gen.nuclear_gw = 100.0
    response = build_response(gen, DEFAULT_DEMAND)
    assert response["headline"]["reliability_ok"] is True


def test_nuclear_renaissance_preset_sized_and_priced_as_requested():
    gen = PRESETS["nuclear_renaissance"]["generation"]
    assert 75.0 <= gen.nuclear_gw <= 85.0
    assert 55.0 <= gen.nuclear_price <= 65.0
    response = build_response(gen, DEFAULT_DEMAND)
    assert response["headline"]["reliability_ok"] is True
    assert response["headline"]["generation_share_pct"]["nuclear"] > 90.0


def test_default_mix_matches_requested_headline_prices():
    gen = DEFAULT_GENERATION
    response = build_response(gen, DEFAULT_DEMAND)
    headline = response["headline"]
    assert gen.wind_offshore_gw == 17.0
    assert gen.wind_onshore_gw == 16.0
    assert gen.solar_roof_gw == 14.0
    assert gen.solar_field_gw == 9.0
    assert gen.gas_gw == 35.0
    assert gen.nuclear_gw == 5.9
    assert gen.nuclear_price == 75
    assert gen.biomass_gw == 5.5
    assert gen.hydro_gw == 1.9
    assert gen.hydro_price == 80
    assert gen.other_storage_gw == 2.8
    assert abs(headline["gas_electricity_price_per_mwh"] - 70.0) < 0.01
    assert (
        abs(
            (headline["offshore_wind_base_price_per_mwh"] + headline["offshore_wind_distribution_cost_per_mwh"])
            - 91.0
        )
        < 0.5
    )
    # battery_gw defaults to ~10 GWh of energy at the assumed 1.5h duration
    assert abs(gen.battery_gw * 1.5 - 10.0) < 0.5


def test_daily_records_expose_unmet_demand_for_shortfall_chart():
    zero_gen = DEFAULT_GENERATION.model_copy(deep=True)
    for field_name in zero_gen.model_fields:
        if field_name.endswith("_gw"):
            setattr(zero_gen, field_name, 0.0)
    response = build_response(zero_gen, DEFAULT_DEMAND)
    assert all("unmet_demand_mwh" in day for day in response["daily"])
    assert all(day["unmet_demand_mwh"] > 0 for day in response["daily"])
    assert sum(day["unmet_demand_mwh"] for day in response["daily"]) == pytest.approx(
        response["headline"]["total_unmet_demand_mwh"], rel=0.01
    )


def test_ac_demand_only_in_summer():
    from app.models import DemandConfig
    from app.simulation import build_demand_mwh

    demand = DemandConfig(heat_pump_pct=0, ev_pct=0, industry_pct=0, ac_pct=100)
    baseline = DemandConfig(heat_pump_pct=0, ev_pct=0, industry_pct=0, ac_pct=0)
    day_mwh, night_mwh = build_demand_mwh(demand)
    base_day_mwh, base_night_mwh = build_demand_mwh(baseline)

    winter_day_idx = 0  # Jan 1st
    summer_day_idx = 200  # ~mid July

    assert abs((day_mwh[winter_day_idx] - base_day_mwh[winter_day_idx])) < 1.0
    assert (day_mwh[summer_day_idx] - base_day_mwh[summer_day_idx]) > 1.0

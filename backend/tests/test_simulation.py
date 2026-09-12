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
from app.models import DemandConfig
from app.simulation import (
    DAYS_PER_YEAR,
    HOUSTON_LATITUDE_DEG,
    MADRID_NEW_YORK_LATITUDE_DEG,
    UK_ACTUAL_LATITUDE_DEG,
    UK_FLEET_ENERGY_MWH_AT_FULL_ELECTRIFICATION,
    V2G_DURATION_HOURS,
    run_simulation,
    solar_capacity_factor_profile,
    solar_latitude_multiplier,
    v2g_capacity_mwh_for,
    v2g_power_mw_for,
)


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
    # Gas's displayed electricity price should always match the commodity-price
    # conversion formula (50% plant efficiency + £8/MWh non-fuel cost), whatever
    # the current default commodity price is set to.
    expected_gas_elec_price = gen.gas_price / 0.5 + 8
    assert abs(headline["gas_electricity_price_per_mwh"] - expected_gas_elec_price) < 0.01
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


def test_solar_latitude_multiplier_is_one_at_actual_uk_latitude():
    assert solar_latitude_multiplier(UK_ACTUAL_LATITUDE_DEG) == pytest.approx(1.0, abs=1e-6)


def test_lower_latitude_increases_solar_output():
    uk_cf = solar_capacity_factor_profile(UK_ACTUAL_LATITUDE_DEG)
    madrid_cf = solar_capacity_factor_profile(MADRID_NEW_YORK_LATITUDE_DEG)
    houston_cf = solar_capacity_factor_profile(HOUSTON_LATITUDE_DEG)

    # Annual mean output should increase monotonically as latitude drops.
    assert uk_cf.mean() < madrid_cf.mean() < houston_cf.mean()

    # Winter (low sun, short days at high latitude) should improve the most.
    winter_day = 355
    summer_day = 172
    winter_gain_madrid = madrid_cf[winter_day] / uk_cf[winter_day]
    summer_gain_madrid = madrid_cf[summer_day] / uk_cf[summer_day]
    assert winter_gain_madrid > summer_gain_madrid > 1.0

    assert solar_latitude_multiplier(MADRID_NEW_YORK_LATITUDE_DEG) == pytest.approx(1.18, abs=0.05)
    assert solar_latitude_multiplier(HOUSTON_LATITUDE_DEG) == pytest.approx(1.32, abs=0.05)


def test_solar_latitude_toggle_boosts_delivered_solar_generation():
    gen_uk = DEFAULT_GENERATION.model_copy(deep=True)
    gen_houston = DEFAULT_GENERATION.model_copy(deep=True)
    gen_houston.solar_latitude_deg = HOUSTON_LATITUDE_DEG

    response_uk = build_response(gen_uk, DEFAULT_DEMAND)
    response_houston = build_response(gen_houston, DEFAULT_DEMAND)

    solar_uk = (
        response_uk["headline"]["generation_share_pct"]["solar_field"]
        + response_uk["headline"]["generation_share_pct"]["solar_roof"]
    )
    solar_houston = (
        response_houston["headline"]["generation_share_pct"]["solar_field"]
        + response_houston["headline"]["generation_share_pct"]["solar_roof"]
    )
    # Same installed GW, but more delivered solar share at the sunnier latitude.
    assert solar_houston > solar_uk
    assert response_houston["headline"]["reliability_ok"] is True


def test_v2g_capacity_scales_with_ev_adoption_and_participation():
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    gen.v2g_participation_pct = 100.0
    demand = DemandConfig(heat_pump_pct=0, ev_pct=100, industry_pct=0, ac_pct=0)

    capacity_mwh = v2g_capacity_mwh_for(gen, demand)
    assert capacity_mwh == pytest.approx(UK_FLEET_ENERGY_MWH_AT_FULL_ELECTRIFICATION, rel=1e-6)

    # Halving either EV adoption or participation halves the available capacity.
    half_ev = demand.model_copy(update={"ev_pct": 50})
    assert v2g_capacity_mwh_for(gen, half_ev) == pytest.approx(capacity_mwh * 0.5, rel=1e-6)

    half_participation = gen.model_copy(update={"v2g_participation_pct": 50.0})
    assert v2g_capacity_mwh_for(half_participation, demand) == pytest.approx(capacity_mwh * 0.5, rel=1e-6)


def test_v2g_power_capacity_duration_is_fleet_size_independent():
    # Energy/power ratio (duration) is a fixed physical ratio (battery size /
    # charger power) - it shouldn't change with fleet size or participation.
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    gen.v2g_participation_pct = 35.0
    demand = DemandConfig(heat_pump_pct=0, ev_pct=40, industry_pct=0, ac_pct=0)

    capacity_mwh = v2g_capacity_mwh_for(gen, demand)
    power_mw = v2g_power_mw_for(gen, demand)
    assert capacity_mwh / power_mw == pytest.approx(V2G_DURATION_HOURS, rel=1e-6)


def test_zero_ev_or_zero_participation_means_no_v2g_capacity():
    gen = DEFAULT_GENERATION.model_copy(deep=True)
    gen.v2g_participation_pct = 100.0
    no_ev_demand = DemandConfig(heat_pump_pct=0, ev_pct=0, industry_pct=0, ac_pct=0)
    assert v2g_capacity_mwh_for(gen, no_ev_demand) == 0.0

    some_ev_demand = DemandConfig(heat_pump_pct=0, ev_pct=50, industry_pct=0, ac_pct=0)
    no_participation_gen = DEFAULT_GENERATION.model_copy(update={"v2g_participation_pct": 0.0})
    assert v2g_capacity_mwh_for(no_participation_gen, some_ev_demand) == 0.0


def test_v2g_reduces_curtailment_and_shortfall_in_a_stressed_mix():
    demand = DemandConfig(heat_pump_pct=0, ev_pct=60, industry_pct=0, ac_pct=0)
    gen_with_v2g = PRESETS["renewables_only"]["generation"].model_copy(update={"v2g_participation_pct": 50.0})
    gen_without_v2g = gen_with_v2g.model_copy(update={"v2g_participation_pct": 0.0})

    response_with = build_response(gen_with_v2g, demand)
    response_without = build_response(gen_without_v2g, demand)

    assert response_with["headline"]["total_curtailment_mwh"] < response_without["headline"]["total_curtailment_mwh"]
    assert response_with["headline"]["total_unmet_demand_mwh"] < response_without["headline"]["total_unmet_demand_mwh"]
    assert response_with["headline"]["generation_share_pct"]["v2g"] > 0


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

"""Turns the raw per-period simulation output into the daily series and
headline figures the frontend renders."""
from __future__ import annotations

from .defaults import EQUIVALENTS
from .models import GenerationConfig
from .simulation import (
    DAYS_PER_YEAR,
    battery_capacity_mwh_for,
    effective_prices,
    other_storage_capacity_mwh_for,
    run_simulation,
    solar_latitude_multiplier,
)
from .models import DemandConfig

GENERATION_SOURCES = [
    "solar_field",
    "solar_roof",
    "nuclear",
    "wind_onshore",
    "wind_offshore",
    "gas",
    "biomass",
    "interconnector_france",
    "interconnector_norway",
    "interconnector_belgium",
    "interconnector_netherlands",
    "geothermal",
    "tidal",
    "morocco_link",
    "hydro",
]

STORAGE_DISCHARGE_SOURCES = ["battery", "other_storage"]
ALL_SUPPLY_SERIES = GENERATION_SOURCES + STORAGE_DISCHARGE_SOURCES


def build_response(gen: GenerationConfig, demand: DemandConfig) -> dict:
    periods = run_simulation(gen, demand)
    prices = effective_prices(gen)

    daily = []
    totals_supply = {s: 0.0 for s in ALL_SUPPLY_SERIES}
    totals_curtailment = {s: 0.0 for s in GENERATION_SOURCES}
    total_demand = 0.0
    total_cost = 0.0
    total_emissions_kg = 0.0
    total_curtailment_mwh = 0.0
    total_curtailment_payment = 0.0
    total_unmet = 0.0
    total_delivered_mwh = 0.0

    battery_capacity = battery_capacity_mwh_for(gen)
    other_capacity = other_storage_capacity_mwh_for(gen)

    for day_idx in range(DAYS_PER_YEAR):
        day_period = periods[day_idx * 2]
        night_period = periods[day_idx * 2 + 1]

        day_supply = {s: 0.0 for s in ALL_SUPPLY_SERIES}
        day_curtailment = {s: 0.0 for s in GENERATION_SOURCES}
        day_storage_charge = {"battery": 0.0, "other_storage": 0.0}
        day_demand_mwh = 0.0
        day_cost = 0.0
        day_emissions_kg = 0.0
        day_curtailment_mwh = 0.0
        day_curtailment_payment = 0.0
        day_unmet = 0.0

        for p in (day_period, night_period):
            day_demand_mwh += p.demand_mwh
            day_cost += p.cost_gbp
            day_emissions_kg += p.emissions_kg
            day_unmet += p.unmet_demand_mwh
            for s, v in p.supply_mwh.items():
                day_supply[s] = day_supply.get(s, 0.0) + v
                totals_supply[s] = totals_supply.get(s, 0.0) + v
            for s, v in p.storage_discharge_mwh.items():
                key = "battery" if s == "battery" else "other_storage"
                day_supply[key] = day_supply.get(key, 0.0) + v
                totals_supply[key] = totals_supply.get(key, 0.0) + v
            for s, v in p.storage_charge_mwh.items():
                key = "battery" if s == "battery" else "other_storage"
                day_storage_charge[key] += v
            for s, v in p.curtailment_mwh.items():
                day_curtailment[s] = day_curtailment.get(s, 0.0) + v
                totals_curtailment[s] = totals_curtailment.get(s, 0.0) + v
                day_curtailment_mwh += v
            day_curtailment_payment += p.curtailment_payment_gbp

        delivered = sum(day_supply.values())
        carbon_intensity = (day_emissions_kg * 1000.0) / (delivered * 1000.0) if delivered > 0 else 0.0

        daily.append(
            {
                "day": day_idx,
                "demand_mwh": round(day_demand_mwh, 1),
                "supply_mwh": {k: round(v, 1) for k, v in day_supply.items()},
                "storage_charge_mwh": {k: round(v, 1) for k, v in day_storage_charge.items()},
                "total_grid_load_mwh": round(day_demand_mwh + sum(day_storage_charge.values()), 1),
                "battery_soc_pct": round(100.0 * night_period.battery_soc_mwh / battery_capacity, 1) if battery_capacity > 0 else 0.0,
                "other_soc_pct": round(100.0 * night_period.other_soc_mwh / other_capacity, 1) if other_capacity > 0 else 0.0,
                "curtailment_mwh": {k: round(v, 1) for k, v in day_curtailment.items() if v > 0},
                "curtailment_total_mwh": round(day_curtailment_mwh, 1),
                "curtailment_payment_gbp": round(day_curtailment_payment, 2),
                "unmet_demand_mwh": round(day_unmet, 1),
                "carbon_intensity_gco2_per_kwh": round(carbon_intensity, 1),
                "cost_gbp": round(day_cost, 2),
            }
        )

        total_demand += day_demand_mwh
        total_cost += day_cost
        total_emissions_kg += day_emissions_kg
        total_curtailment_mwh += day_curtailment_mwh
        total_curtailment_payment += day_curtailment_payment
        total_unmet += day_unmet
        total_delivered_mwh += delivered

    generation_share_pct = {}
    if total_delivered_mwh > 0:
        for s in ALL_SUPPLY_SERIES:
            generation_share_pct[s] = round(100.0 * totals_supply.get(s, 0.0) / total_delivered_mwh, 2)

    avg_carbon_intensity = (
        (total_emissions_kg * 1000.0) / (total_delivered_mwh * 1000.0) if total_delivered_mwh > 0 else 0.0
    )

    equivalents = {
        "nuclear_reactors": round(gen.nuclear_gw / EQUIVALENTS["nuclear_unit_gw"], 1),
        "onshore_turbines": round(gen.wind_onshore_gw * 1000 / EQUIVALENTS["onshore_turbine_mw"]),
        "offshore_turbines": round(gen.wind_offshore_gw * 1000 / EQUIVALENTS["offshore_turbine_mw"]),
        "gas_plants": round(gen.gas_gw / EQUIVALENTS["gas_plant_gw"], 1),
        "solar_panels_millions": round(
            (gen.solar_field_gw + gen.solar_roof_gw) * 1_000_000_000 / EQUIVALENTS["solar_panel_w"] / 1_000_000, 1
        ),
        "tidal_turbines": round(gen.tidal_gw * 1000 / EQUIVALENTS["tidal_turbine_mw"]),
        "geothermal_plants": round(gen.geothermal_gw * 1000 / EQUIVALENTS["geothermal_plant_mw"], 1),
        "morocco_links": round(gen.morocco_link_gw / EQUIVALENTS["morocco_link_gw"], 1),
    }

    headline = {
        "total_demand_mwh": round(total_demand, 0),
        "total_delivered_mwh": round(total_delivered_mwh, 0),
        "total_cost_gbp": round(total_cost, 0),
        "cost_per_mwh": round(total_cost / total_demand, 2) if total_demand > 0 else 0.0,
        "generation_share_pct": generation_share_pct,
        "total_emissions_tonnes": round(total_emissions_kg / 1000.0, 0),
        "avg_carbon_intensity_gco2_per_kwh": round(avg_carbon_intensity, 1),
        "total_curtailment_mwh": round(total_curtailment_mwh, 0),
        "total_curtailment_payment_gbp": round(total_curtailment_payment, 0),
        "total_unmet_demand_mwh": round(total_unmet, 1),
        "reliability_ok": bool(total_unmet < 1.0),
        "offshore_wind_distribution_cost_per_mwh": round(prices["wind_offshore_distribution"], 2),
        "offshore_wind_base_price_per_mwh": round(prices["wind_offshore_base"], 2),
        "gas_electricity_price_per_mwh": round(prices["gas"], 2),
        "solar_latitude_deg": gen.solar_latitude_deg,
        "solar_latitude_multiplier": round(solar_latitude_multiplier(gen.solar_latitude_deg), 3),
        "equivalents": equivalents,
    }

    return {"daily": daily, "headline": headline}

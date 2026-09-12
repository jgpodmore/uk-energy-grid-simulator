"""Core grid simulation engine.

Models 365 days, each split into a 12h "day" period and a 12h "night"
period (730 periods total). For every period we compute:

  * demand (base seasonal demand + electrification add-ons)
  * available generation from each source (weather/season/time-of-day
    dependent for solar & wind, flat for nuclear, "on demand up to
    capacity" for dispatchable sources)
  * a merit-order dispatch of the dispatchable sources (cheapest first)
  * storage charging (when there's a surplus) / discharging (when there's
    a shortfall)
  * curtailment (surplus that storage can't absorb)
  * unmet demand (shortfall that dispatchable generation + storage can't cover)
  * cost and CO2 emissions

All figures are illustrative approximations, not official statistics.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .models import DemandConfig, GenerationConfig

DAYS_PER_YEAR = 365
HOURS_PER_PERIOD = 12.0

# gCO2 per kWh - standard "carbon intensity" convention (as used by GB's
# carbonintensity.org.uk), not gCO2/MWh, to keep numbers on a familiar scale.
EMISSION_FACTORS_GCO2_PER_KWH = {
    "solar_field": 41,
    "solar_roof": 41,
    "nuclear": 12,
    "wind_onshore": 11,
    "wind_offshore": 12,
    "gas": 400,
    "biomass": 120,
    "interconnector_france": 50,
    "interconnector_norway": 20,
    "interconnector_belgium": 150,
    "interconnector_netherlands": 300,
    "geothermal": 38,
    "tidal": 14,
    "morocco_link": 45,
    "hydro": 10,
}

# Availability factors for "always available up to capacity" dispatchable sources
DISPATCHABLE_AVAILABILITY = {
    "gas": 0.90,
    "biomass": 0.88,
    "interconnector_france": 0.85,
    "interconnector_norway": 0.85,
    "interconnector_belgium": 0.85,
    "interconnector_netherlands": 0.85,
    # A single very long HVDC link - firm delivery is underpinned by
    # co-located Moroccan solar/wind + storage, modelled like an interconnector.
    "morocco_link": 0.85,
}

NUCLEAR_AVAILABILITY = 0.90
# Enhanced geothermal (EGS) taps deep heat anywhere, so - like nuclear - it
# runs as flat baseload regardless of weather or season.
GEOTHERMAL_AVAILABILITY = 0.90

GAS_EFFICIENCY = 0.50
GAS_NON_FUEL_COST_PER_MWH = 8.0

# Offshore wind grid/distribution cost: flat base + scaling with capacity,
# because more offshore capacity needs more transmission reinforcement.
OFFSHORE_DISTRIBUTION_BASE = 5.0
OFFSHORE_DISTRIBUTION_PER_GW = 0.5
# Onshore's distribution cost is small and is simply folded into its price slider.

BATTERY_DURATION_HOURS = 1.5
BATTERY_EFFICIENCY = 0.88
OTHER_STORAGE_DURATION_HOURS = 10.7
OTHER_STORAGE_EFFICIENCY = 0.75

# Curtailment priority: cheapest-to-turn-down / most-flexible first. Nuclear
# and geothermal (least flexible baseload) are curtailed last, if at all.
CURTAILMENT_ORDER = [
    "wind_offshore",
    "wind_onshore",
    "tidal",
    "hydro",
    "solar_field",
    "solar_roof",
    "geothermal",
    "nuclear",
]

# Merit order dispatch tie-break categories (actual order computed by price)
DISPATCHABLE_SOURCES = [
    "gas",
    "biomass",
    "interconnector_france",
    "interconnector_norway",
    "interconnector_belgium",
    "interconnector_netherlands",
    "morocco_link",
]

# ---------------------------------------------------------------------------
# Seasonal / weather profile generation
# ---------------------------------------------------------------------------

_WEATHER_SEED = 42


def _seasonal(day_index: np.ndarray, peak_day: float, mean: float, amplitude: float) -> np.ndarray:
    return mean + amplitude * np.cos(2 * np.pi * (day_index - peak_day) / DAYS_PER_YEAR)


@dataclass
class WeatherYear:
    """Precomputed, deterministic capacity-factor profiles for a year.

    Generated once with a fixed random seed so that moving a price slider
    doesn't make the weather jump around - only capacity/cost changes
    affect results, exactly as if we simulated the same weather year twice.
    """

    wind_onshore_cf: np.ndarray  # (365, 2) [day, night]
    wind_offshore_cf: np.ndarray  # (365, 2)
    tidal_cf: np.ndarray  # (365,) same value used for day & night - see note below
    hydro_cf: np.ndarray  # (365,) same value used for day & night - river flow doesn't care about time of day

    @staticmethod
    def build(seed: int = _WEATHER_SEED) -> "WeatherYear":
        days = np.arange(DAYS_PER_YEAR)
        rng = np.random.default_rng(seed)

        # Wind: seasonal mean capacity factor, peaking in winter (day ~355),
        # plus day-to-day intermittency noise (independently for day/night).
        onshore_seasonal = _seasonal(days, peak_day=355, mean=0.275, amplitude=0.075)
        offshore_seasonal = _seasonal(days, peak_day=355, mean=0.40, amplitude=0.10)

        def with_noise(seasonal: np.ndarray) -> np.ndarray:
            noise = rng.normal(loc=1.0, scale=0.35, size=(DAYS_PER_YEAR, 2))
            noise = np.clip(noise, 0.0, 2.0)
            cf = seasonal[:, None] * noise
            return np.clip(cf, 0.0, 0.95)

        wind_onshore_cf = with_noise(onshore_seasonal)
        wind_offshore_cf = with_noise(offshore_seasonal)

        # Tidal: unlike wind, tidal flow is fully predictable - not random -
        # but it isn't flat like nuclear either. It follows the ~14.77 day
        # spring/neap cycle (bigger tides, more energy, around new/full moon).
        # Individual high/low tides shift ~50 minutes later each day and so
        # drift across our fixed 12h day/night split; averaged over each
        # 12h block that drift roughly cancels out, so we apply the same
        # spring/neap-modulated capacity factor to both periods of a day.
        tidal_cf = 0.35 + 0.12 * np.cos(2 * np.pi * days / 14.765)
        tidal_cf = np.clip(tidal_cf, 0.0, 0.6)

        # Hydro (natural flow / run-of-river): output tracks rainfall and
        # river flow, which is highest in the wet, low-evaporation winter
        # months and lowest in summer - same seasonal shape as wind, but
        # deterministic rather than randomly intermittent.
        hydro_cf = _seasonal(days, peak_day=355, mean=0.40, amplitude=0.15)
        hydro_cf = np.clip(hydro_cf, 0.1, 0.75)

        return WeatherYear(
            wind_onshore_cf=wind_onshore_cf,
            wind_offshore_cf=wind_offshore_cf,
            tidal_cf=tidal_cf,
            hydro_cf=hydro_cf,
        )


_WEATHER_YEAR = WeatherYear.build()


# ---------------------------------------------------------------------------
# Solar geometry: capacity factor as a function of latitude
# ---------------------------------------------------------------------------
#
# Solar's seasonal profile above was tuned to the UK's actual latitude. To
# let users compare against a sunnier latitude (e.g. "what if Britain were
# where Madrid or Houston are?"), we derive the day/latitude dependent
# capacity factor from the standard astronomical formula for daily
# extraterrestrial irradiation (Cooper's equation for solar declination,
# then the daylength/sun-angle integral - the same geometry behind any solar
# resource textbook). This isolates the pure "latitude effect" - a lower
# latitude gets a higher midday sun angle and, especially, much less of a
# winter slump - while deliberately still ignoring weather/cloud cover, for
# consistency with solar's "ignore weather, fixed per day" simplification
# above. Real Madrid/Houston are also sunnier than this because they're
# drier and less cloudy than the UK - this only captures the geometric part.

UK_ACTUAL_LATITUDE_DEG = 51.5  # London - the UK's "actual" reference latitude
MADRID_NEW_YORK_LATITUDE_DEG = 40.0
HOUSTON_LATITUDE_DEG = 30.0

SOLAR_LATITUDE_PRESETS = {
    "actual": {"label": "Actual UK latitude", "sublabel": "~51.5°N, London", "value": UK_ACTUAL_LATITUDE_DEG},
    "madrid_nyc": {"label": "Madrid / New York latitude", "sublabel": "~40°N", "value": MADRID_NEW_YORK_LATITUDE_DEG},
    "houston": {"label": "Houston latitude", "sublabel": "~30°N", "value": HOUSTON_LATITUDE_DEG},
}

# The mean capacity factor solar was originally hand-tuned to at the UK's
# actual latitude - used to calibrate the astronomical model onto the same
# scale, so "actual" behaves exactly as it always has.
_SOLAR_CF_MEAN_AT_UK_LATITUDE = 0.175


def _relative_extraterrestrial_irradiance(latitude_deg: float, days: np.ndarray) -> np.ndarray:
    declination_deg = 23.45 * np.sin(np.deg2rad(360.0 / DAYS_PER_YEAR * (284 + days)))
    phi = np.deg2rad(latitude_deg)
    delta = np.deg2rad(declination_deg)
    cos_sunset_angle = np.clip(-np.tan(phi) * np.tan(delta), -1.0, 1.0)
    sunset_angle = np.arccos(cos_sunset_angle)
    return sunset_angle * np.sin(phi) * np.sin(delta) + np.cos(phi) * np.cos(delta) * np.sin(sunset_angle)


_SOLAR_CF_CALIBRATION = _SOLAR_CF_MEAN_AT_UK_LATITUDE / _relative_extraterrestrial_irradiance(
    UK_ACTUAL_LATITUDE_DEG, np.arange(DAYS_PER_YEAR)
).mean()


def solar_capacity_factor_profile(latitude_deg: float) -> np.ndarray:
    """Daytime solar capacity factor for each of the 365 days, at the given latitude."""
    days = np.arange(DAYS_PER_YEAR)
    cf = _SOLAR_CF_CALIBRATION * _relative_extraterrestrial_irradiance(latitude_deg, days)
    return np.clip(cf, 0.02, 0.45)


def solar_latitude_multiplier(latitude_deg: float) -> float:
    """How much more (or less) annual solar output a panel would deliver at this
    latitude versus the UK's actual latitude, from geometry alone."""
    at_latitude = solar_capacity_factor_profile(latitude_deg).mean()
    at_uk = solar_capacity_factor_profile(UK_ACTUAL_LATITUDE_DEG).mean()
    return at_latitude / at_uk


# ---------------------------------------------------------------------------
# Demand profile generation
# ---------------------------------------------------------------------------

BASE_DEMAND_MEAN_GWH_PER_DAY = 800.0
BASE_DEMAND_AMPLITUDE_GWH_PER_DAY = 160.0
BASE_DEMAND_PEAK_DAY = 15  # mid January
BASE_DAY_SHARE = 0.58
BASE_NIGHT_SHARE = 0.42

# Target annual demand (MWh) added at 100% adoption for each electrification lever.
HEAT_PUMP_FULL_TWH = 90.0
EV_FULL_TWH = 95.0
INDUSTRY_FULL_TWH = 50.0
AC_FULL_TWH = 20.0

AC_MONTH_START_DAY = 121  # ~May 1
AC_MONTH_END_DAY = 273  # ~Sep 30


def _normalized_shape_mwh(shape: np.ndarray, target_twh: float) -> np.ndarray:
    total = shape.sum()
    if total <= 0:
        return np.zeros_like(shape)
    return shape / total * target_twh * 1_000_000.0  # TWh -> MWh


def build_demand_mwh(demand: DemandConfig) -> tuple[np.ndarray, np.ndarray]:
    """Returns (day_mwh, night_mwh) arrays of length 365."""
    days = np.arange(DAYS_PER_YEAR)

    base_daily_gwh = _seasonal(
        days, peak_day=BASE_DEMAND_PEAK_DAY, mean=BASE_DEMAND_MEAN_GWH_PER_DAY, amplitude=BASE_DEMAND_AMPLITUDE_GWH_PER_DAY
    )
    base_daily_mwh = base_daily_gwh * 1000.0
    day_mwh = base_daily_mwh * BASE_DAY_SHARE
    night_mwh = base_daily_mwh * BASE_NIGHT_SHARE

    # Heat pumps: strongly winter-weighted (heating demand), split ~50/50 day/night.
    heat_shape = np.clip(_seasonal(days, peak_day=15, mean=1.0, amplitude=0.9), 0.05, None)
    heat_annual_mwh = _normalized_shape_mwh(heat_shape, HEAT_PUMP_FULL_TWH * demand.heat_pump_pct / 100.0)
    day_mwh = day_mwh + heat_annual_mwh * 0.50
    night_mwh = night_mwh + heat_annual_mwh * 0.50

    # EVs: flat across the year, mostly overnight charging.
    ev_shape = np.ones(DAYS_PER_YEAR)
    ev_annual_mwh = _normalized_shape_mwh(ev_shape, EV_FULL_TWH * demand.ev_pct / 100.0)
    day_mwh = day_mwh + ev_annual_mwh * 0.30
    night_mwh = night_mwh + ev_annual_mwh * 0.70

    # Industry: flat across the year, mostly daytime shifts.
    industry_shape = np.ones(DAYS_PER_YEAR)
    industry_annual_mwh = _normalized_shape_mwh(industry_shape, INDUSTRY_FULL_TWH * demand.industry_pct / 100.0)
    day_mwh = day_mwh + industry_annual_mwh * 0.60
    night_mwh = night_mwh + industry_annual_mwh * 0.40

    # Air conditioning: only May-September, mostly daytime.
    ac_shape = np.where((days >= AC_MONTH_START_DAY) & (days <= AC_MONTH_END_DAY), 1.0, 0.0)
    ac_annual_mwh = _normalized_shape_mwh(ac_shape, AC_FULL_TWH * demand.ac_pct / 100.0)
    day_mwh = day_mwh + ac_annual_mwh * 0.90
    night_mwh = night_mwh + ac_annual_mwh * 0.10

    return day_mwh, night_mwh


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


@dataclass
class PeriodResult:
    day: int
    period: str  # "day" | "night"
    demand_mwh: float
    supply_mwh: dict = field(default_factory=dict)
    storage_charge_mwh: dict = field(default_factory=dict)
    storage_discharge_mwh: dict = field(default_factory=dict)
    battery_soc_mwh: float = 0.0
    other_soc_mwh: float = 0.0
    curtailment_mwh: dict = field(default_factory=dict)
    curtailment_payment_gbp: float = 0.0
    unmet_demand_mwh: float = 0.0
    cost_gbp: float = 0.0
    emissions_kg: float = 0.0


def effective_prices(gen: GenerationConfig) -> dict:
    gas_elec_price = gen.gas_price / GAS_EFFICIENCY + GAS_NON_FUEL_COST_PER_MWH
    offshore_distribution = OFFSHORE_DISTRIBUTION_BASE + OFFSHORE_DISTRIBUTION_PER_GW * gen.wind_offshore_gw
    offshore_total = gen.wind_offshore_price + offshore_distribution
    return {
        "solar_field": gen.solar_field_price,
        "solar_roof": gen.solar_roof_price,
        "nuclear": gen.nuclear_price,
        "wind_onshore": gen.wind_onshore_price,
        "wind_offshore": offshore_total,
        "wind_offshore_distribution": offshore_distribution,
        "wind_offshore_base": gen.wind_offshore_price,
        "gas": gas_elec_price,
        "biomass": gen.biomass_price,
        "interconnector_france": gen.interconnector_france_price,
        "interconnector_norway": gen.interconnector_norway_price,
        "interconnector_belgium": gen.interconnector_belgium_price,
        "interconnector_netherlands": gen.interconnector_netherlands_price,
        "geothermal": gen.geothermal_price,
        "tidal": gen.tidal_price,
        "morocco_link": gen.morocco_link_price,
        "hydro": gen.hydro_price,
    }


def run_simulation(gen: GenerationConfig, demand: DemandConfig) -> list[PeriodResult]:
    prices = effective_prices(gen)
    day_demand_mwh, night_demand_mwh = build_demand_mwh(demand)
    solar_cf_profile = solar_capacity_factor_profile(gen.solar_latitude_deg)

    battery_capacity_mwh = gen.battery_gw * 1000 * BATTERY_DURATION_HOURS
    other_capacity_mwh = gen.other_storage_gw * 1000 * OTHER_STORAGE_DURATION_HOURS
    battery_power_mwh_per_period = gen.battery_gw * 1000 * HOURS_PER_PERIOD
    other_power_mwh_per_period = gen.other_storage_gw * 1000 * HOURS_PER_PERIOD

    battery_soc = battery_capacity_mwh * 0.5
    other_soc = other_capacity_mwh * 0.5

    results: list[PeriodResult] = []

    for day_idx in range(DAYS_PER_YEAR):
        for period_name, demand_mwh in (("day", day_demand_mwh[day_idx]), ("night", night_demand_mwh[day_idx])):
            is_day = period_name == "day"

            # --- Must-run availability for this period ---
            must_run_mwh = {}
            must_run_mwh["nuclear"] = gen.nuclear_gw * 1000 * HOURS_PER_PERIOD * NUCLEAR_AVAILABILITY

            solar_cf = solar_cf_profile[day_idx] if is_day else 0.0
            must_run_mwh["solar_field"] = gen.solar_field_gw * 1000 * HOURS_PER_PERIOD * solar_cf
            must_run_mwh["solar_roof"] = gen.solar_roof_gw * 1000 * HOURS_PER_PERIOD * solar_cf

            wind_period_idx = 0 if is_day else 1
            onshore_cf = _WEATHER_YEAR.wind_onshore_cf[day_idx, wind_period_idx]
            offshore_cf = _WEATHER_YEAR.wind_offshore_cf[day_idx, wind_period_idx]
            must_run_mwh["wind_onshore"] = gen.wind_onshore_gw * 1000 * HOURS_PER_PERIOD * onshore_cf
            must_run_mwh["wind_offshore"] = gen.wind_offshore_gw * 1000 * HOURS_PER_PERIOD * offshore_cf

            must_run_mwh["geothermal"] = gen.geothermal_gw * 1000 * HOURS_PER_PERIOD * GEOTHERMAL_AVAILABILITY

            tidal_cf = _WEATHER_YEAR.tidal_cf[day_idx]
            must_run_mwh["tidal"] = gen.tidal_gw * 1000 * HOURS_PER_PERIOD * tidal_cf

            hydro_cf = _WEATHER_YEAR.hydro_cf[day_idx]
            must_run_mwh["hydro"] = gen.hydro_gw * 1000 * HOURS_PER_PERIOD * hydro_cf

            total_must_run = sum(must_run_mwh.values())

            supply_mwh: dict[str, float] = dict(must_run_mwh)
            storage_charge: dict[str, float] = {}
            storage_discharge: dict[str, float] = {}
            curtailment: dict[str, float] = {}
            curtailment_payment = 0.0
            unmet = 0.0
            cost = 0.0

            residual = demand_mwh - total_must_run

            if residual >= 0:
                # Dispatch dispatchable sources in ascending price (merit) order.
                dispatch_caps = {
                    "gas": gen.gas_gw,
                    "biomass": gen.biomass_gw,
                    "interconnector_france": gen.interconnector_france_gw,
                    "interconnector_norway": gen.interconnector_norway_gw,
                    "interconnector_belgium": gen.interconnector_belgium_gw,
                    "interconnector_netherlands": gen.interconnector_netherlands_gw,
                    "morocco_link": gen.morocco_link_gw,
                }
                order = sorted(DISPATCHABLE_SOURCES, key=lambda s: prices[s])
                remaining = residual
                for source in order:
                    if remaining <= 1e-9:
                        break
                    capacity_mwh = dispatch_caps[source] * 1000 * HOURS_PER_PERIOD * DISPATCHABLE_AVAILABILITY[source]
                    take = min(capacity_mwh, remaining)
                    if take > 0:
                        supply_mwh[source] = supply_mwh.get(source, 0.0) + take
                        remaining -= take

                if remaining > 1e-9:
                    # Draw down storage: batteries first, then long-duration storage.
                    batt_take = min(battery_soc, battery_power_mwh_per_period, remaining) * BATTERY_EFFICIENCY
                    # discharge draws down SoC by the raw amount, delivers batt_take to grid
                    if batt_take > 0:
                        raw_draw = batt_take / BATTERY_EFFICIENCY
                        battery_soc -= raw_draw
                        storage_discharge["battery"] = batt_take
                        remaining -= batt_take

                if remaining > 1e-9:
                    other_take = min(other_soc, other_power_mwh_per_period, remaining) * OTHER_STORAGE_EFFICIENCY
                    if other_take > 0:
                        raw_draw = other_take / OTHER_STORAGE_EFFICIENCY
                        other_soc -= raw_draw
                        storage_discharge["other_storage"] = other_take
                        remaining -= other_take

                if remaining > 1e-9:
                    unmet = remaining

            else:
                surplus = -residual
                # Charge storage: battery first, then other storage.
                batt_room = max(0.0, battery_capacity_mwh - battery_soc)
                batt_charge_raw = min(surplus, battery_power_mwh_per_period, batt_room / BATTERY_EFFICIENCY if BATTERY_EFFICIENCY > 0 else 0.0)
                if batt_charge_raw > 0:
                    battery_soc += batt_charge_raw * BATTERY_EFFICIENCY
                    storage_charge["battery"] = batt_charge_raw
                    surplus -= batt_charge_raw

                other_room = max(0.0, other_capacity_mwh - other_soc)
                other_charge_raw = min(surplus, other_power_mwh_per_period, other_room / OTHER_STORAGE_EFFICIENCY if OTHER_STORAGE_EFFICIENCY > 0 else 0.0)
                if other_charge_raw > 0:
                    other_soc += other_charge_raw * OTHER_STORAGE_EFFICIENCY
                    storage_charge["other_storage"] = other_charge_raw
                    surplus -= other_charge_raw

                if surplus > 1e-9:
                    remaining_curtail = surplus
                    for source in CURTAILMENT_ORDER:
                        if remaining_curtail <= 1e-9:
                            break
                        available = supply_mwh.get(source, 0.0)
                        cut = min(available, remaining_curtail)
                        if cut > 0:
                            supply_mwh[source] -= cut
                            curtailment[source] = curtailment.get(source, 0.0) + cut
                            curtailment_payment += cut * prices[source]
                            remaining_curtail -= cut

            # --- Costs & emissions from what was actually delivered ---
            for source, mwh in supply_mwh.items():
                if mwh <= 0:
                    continue
                cost += mwh * prices[source]
            # storage throughput cost (levelized £/MWh of energy discharged)
            if storage_discharge.get("battery"):
                cost += storage_discharge["battery"] * gen.battery_price
            if storage_discharge.get("other_storage"):
                cost += storage_discharge["other_storage"] * gen.other_storage_price
            cost += curtailment_payment

            emissions_g = 0.0
            for source, mwh in supply_mwh.items():
                if mwh <= 0:
                    continue
                factor = EMISSION_FACTORS_GCO2_PER_KWH.get(source, 0.0)
                emissions_g += mwh * 1000.0 * factor  # MWh -> kWh
            emissions_kg = emissions_g / 1000.0

            results.append(
                PeriodResult(
                    day=day_idx,
                    period=period_name,
                    demand_mwh=demand_mwh,
                    supply_mwh=supply_mwh,
                    storage_charge_mwh=storage_charge,
                    storage_discharge_mwh=storage_discharge,
                    battery_soc_mwh=battery_soc,
                    other_soc_mwh=other_soc,
                    curtailment_mwh=curtailment,
                    curtailment_payment_gbp=curtailment_payment,
                    unmet_demand_mwh=unmet,
                    cost_gbp=cost,
                    emissions_kg=emissions_kg,
                )
            )

    return results


def battery_capacity_mwh_for(gen: GenerationConfig) -> float:
    return gen.battery_gw * 1000 * BATTERY_DURATION_HOURS


def other_storage_capacity_mwh_for(gen: GenerationConfig) -> float:
    return gen.other_storage_gw * 1000 * OTHER_STORAGE_DURATION_HOURS

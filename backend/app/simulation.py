"""Core grid simulation engine.

Models 365 days, each split into 24 hourly periods (8,760 periods total).
For every period we compute:

  * demand (base seasonal demand + electrification add-ons, shaped across
    the day by a realistic hourly load curve)
  * available generation from each source (weather/season/hour-of-day
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

from dataclasses import dataclass, field

import numpy as np

from .models import DemandConfig, GenerationConfig

DAYS_PER_YEAR = 365
HOURS_PER_DAY = 24
HOURS_PER_PERIOD = 1.0

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

# Vehicle-to-grid (V2G): the electrified share of the car fleet forms a large
# but power-constrained battery pool. Its energy capacity scales with how much
# of transport is electrified (the EV demand slider) and how much of that
# fleet's batteries are actually available to the grid (opt-in rate, plugged-in
# availability, allowed depth-of-discharge - all bundled into one participation
# slider). Its power rating is derived from a per-vehicle charger rating, so
# the resulting duration (energy/power) is a fixed physical ratio - a car's
# battery divided by its charger's power - independent of fleet size.
UK_CAR_FLEET_COUNT = 32_000_000  # licensed cars on UK roads, approx.
AVERAGE_EV_BATTERY_KWH = 60.0  # typical modern BEV battery size
V2G_CHARGER_KW = 7.0  # typical single-phase bidirectional home charger
V2G_DURATION_HOURS = AVERAGE_EV_BATTERY_KWH / V2G_CHARGER_KW
V2G_EFFICIENCY = 0.85  # a little lower than dedicated grid batteries
UK_FLEET_ENERGY_MWH_AT_FULL_ELECTRIFICATION = UK_CAR_FLEET_COUNT * AVERAGE_EV_BATTERY_KWH / 1000.0

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

    wind_onshore_cf: np.ndarray  # (365, 24)
    wind_offshore_cf: np.ndarray  # (365, 24)
    tidal_cf: np.ndarray  # (365,) same value used across all 24 hours - see note below
    hydro_cf: np.ndarray  # (365,) same value used across all 24 hours - river flow doesn't care about time of day

    @staticmethod
    def build(seed: int = _WEATHER_SEED) -> "WeatherYear":
        days = np.arange(DAYS_PER_YEAR)
        rng = np.random.default_rng(seed)

        # Wind: seasonal mean capacity factor, peaking in winter (day ~355),
        # plus hour-to-hour intermittency noise.
        onshore_seasonal = _seasonal(days, peak_day=355, mean=0.275, amplitude=0.075)
        offshore_seasonal = _seasonal(days, peak_day=355, mean=0.40, amplitude=0.10)

        def with_noise(seasonal: np.ndarray) -> np.ndarray:
            # Noise is autocorrelated (AR(1)) rather than independent draw-to-draw -
            # real wind tends to stay windy or calm for several hours at a stretch,
            # not swing randomly from one hour to the next. The AR(1) coefficient
            # (0.85) is "variance-preserving": the resulting series still has
            # mean 0, std 1 before being rescaled below, so the overall spread of
            # capacity factors is unchanged from a naive iid draw - only the
            # hour-to-hour persistence improves.
            n = DAYS_PER_YEAR * HOURS_PER_DAY
            innovations = rng.normal(loc=0.0, scale=1.0, size=n)
            alpha = 0.85
            x = np.empty(n)
            x[0] = innovations[0]
            for i in range(1, n):
                x[i] = alpha * x[i - 1] + np.sqrt(1 - alpha**2) * innovations[i]
            noise = np.clip(1.0 + x * 0.35, 0.0, 2.0).reshape(DAYS_PER_YEAR, HOURS_PER_DAY)
            cf = seasonal[:, None] * noise
            return np.clip(cf, 0.0, 0.95)

        wind_onshore_cf = with_noise(onshore_seasonal)
        wind_offshore_cf = with_noise(offshore_seasonal)

        # Tidal: unlike wind, tidal flow is fully predictable - not random -
        # but it isn't flat like nuclear either. It follows the ~14.77 day
        # spring/neap cycle (bigger tides, more energy, around new/full moon).
        # Individual high/low tides shift ~50 minutes later each day and cycle
        # roughly twice a day; modelling that exact timing is more detail than
        # this illustrative model needs, so we apply the same spring/neap-
        # modulated capacity factor across all 24 hours of a day.
        tidal_cf = 0.35 + 0.12 * np.cos(2 * np.pi * days / 14.765)
        tidal_cf = np.clip(tidal_cf, 0.0, 0.6)

        # Hydro (natural flow / run-of-river): output tracks rainfall and
        # river flow, which is highest in the wet, low-evaporation winter
        # months and lowest in summer - same seasonal shape as wind, but
        # deterministic rather than randomly intermittent, and doesn't vary
        # meaningfully hour to hour.
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


def solar_hourly_capacity_factor_profile(latitude_deg: float) -> np.ndarray:
    """Hour-by-hour solar capacity factor for each of the 365 days, at the
    given latitude - shape (365, 24).

    solar_capacity_factor_profile() above gives each day's *mean* capacity
    factor, calibrated against the UK's actual output and the latitude
    toggle. This redistributes that same daily energy budget across the 24
    hours using the sun's actual position that hour (the hour angle and
    zenith angle - the same declination computed above, now applied once
    per hour instead of integrated over the whole day), so sunrise and
    sunset shift realistically with the season and latitude - long summer
    days, short winter ones - while each day's *total* stays exactly what
    it was calibrated to be. Local solar noon is assumed to be 12:00 clock
    time (ignoring the equation of time and exact longitude/timezone
    offset - a reasonable illustrative simplification, same spirit as the
    rest of this model).
    """
    days = np.arange(DAYS_PER_YEAR)
    daily_cf = solar_capacity_factor_profile(latitude_deg)  # (365,)

    declination_deg = 23.45 * np.sin(np.deg2rad(360.0 / DAYS_PER_YEAR * (284 + days)))  # (365,)
    phi = np.deg2rad(latitude_deg)
    delta = np.deg2rad(declination_deg)  # (365,)

    hour_midpoints = np.arange(HOURS_PER_DAY) + 0.5  # (24,)
    hour_angle = np.deg2rad(15.0 * (hour_midpoints - 12.0))  # (24,)

    cos_zenith = (
        np.sin(phi) * np.sin(delta)[:, None]
        + np.cos(phi) * np.cos(delta)[:, None] * np.cos(hour_angle)[None, :]
    )  # (365, 24)
    raw_shape = np.clip(cos_zenith, 0.0, None)

    daily_raw_total = raw_shape.sum(axis=1)  # (365,)
    daily_raw_total_safe = np.where(daily_raw_total > 1e-9, daily_raw_total, 1.0)

    # Spread each day's (mean_cf * 24h) energy budget across daylight hours
    # proportionally to the sun's position that hour.
    return (daily_cf * HOURS_PER_DAY)[:, None] * raw_shape / daily_raw_total_safe[:, None]


# ---------------------------------------------------------------------------
# Demand profile generation
# ---------------------------------------------------------------------------

BASE_DEMAND_MEAN_GWH_PER_DAY = 800.0
BASE_DEMAND_AMPLITUDE_GWH_PER_DAY = 160.0
BASE_DEMAND_PEAK_DAY = 15  # mid January

# Target annual demand (MWh) added at 100% adoption for each electrification lever.
HEAT_PUMP_FULL_TWH = 90.0
EV_FULL_TWH = 95.0
INDUSTRY_FULL_TWH = 50.0
AC_FULL_TWH = 20.0

AC_MONTH_START_DAY = 121  # ~May 1
AC_MONTH_END_DAY = 273  # ~Sep 30


def _normalize_hourly_shape(raw: list[float]) -> np.ndarray:
    """A 24-element relative intraday shape, rescaled to mean 1.0 so it only
    redistributes a day's total within the day rather than changing it."""
    arr = np.array(raw, dtype=float)
    return arr / arr.mean()


# Relative shape of electricity demand across a 24h day (index 0 = the hour
# starting at midnight), loosely matching GB grid's typical daily curve: an
# overnight trough around 3-4am, a morning ramp, a modest midday plateau,
# and an evening peak around 17:00-19:00.
BASE_DEMAND_HOURLY_SHAPE = _normalize_hourly_shape(
    [
        0.78, 0.72, 0.68, 0.67, 0.68, 0.72,
        0.80, 0.92, 1.02, 1.05, 1.05, 1.04,
        1.03, 1.02, 1.02, 1.03, 1.08, 1.18,
        1.25, 1.22, 1.12, 1.02, 0.92, 0.84,
    ]
)

# Heat pumps: a mild morning and evening heating ramp either side of a
# daytime lull, with an overnight setback.
HEAT_PUMP_HOURLY_SHAPE = _normalize_hourly_shape(
    [
        0.85, 0.80, 0.78, 0.78, 0.80, 0.85,
        1.15, 1.35, 1.25, 1.00, 0.90, 0.88,
        0.88, 0.88, 0.90, 0.95, 1.10, 1.30,
        1.35, 1.25, 1.10, 1.00, 0.92, 0.88,
    ]
)

# EVs: dominated by overnight off-peak charging, with a small daytime
# baseline for workplace/public charging.
EV_HOURLY_SHAPE = _normalize_hourly_shape(
    [
        2.2, 2.3, 2.3, 2.2, 2.0, 1.6,
        0.9, 0.5, 0.4, 0.4, 0.4, 0.4,
        0.4, 0.4, 0.4, 0.4, 0.4, 0.5,
        0.6, 0.8, 1.2, 1.8, 2.1, 2.2,
    ]
)

# Industry: a long daytime plateau matching typical shift patterns, low overnight.
INDUSTRY_HOURLY_SHAPE = _normalize_hourly_shape(
    [
        0.35, 0.30, 0.30, 0.30, 0.35, 0.50,
        0.90, 1.25, 1.35, 1.35, 1.35, 1.30,
        1.25, 1.30, 1.35, 1.35, 1.30, 1.20,
        1.00, 0.70, 0.50, 0.40, 0.35, 0.35,
    ]
)

# Air conditioning: tracks temperature with a lag, peaking mid-to-late afternoon.
AC_HOURLY_SHAPE = _normalize_hourly_shape(
    [
        0.25, 0.20, 0.20, 0.20, 0.20, 0.25,
        0.35, 0.50, 0.70, 0.95, 1.25, 1.55,
        1.85, 2.10, 2.25, 2.30, 2.20, 1.95,
        1.60, 1.25, 0.95, 0.70, 0.50, 0.35,
    ]
)


def _normalized_shape_mwh(shape: np.ndarray, target_twh: float) -> np.ndarray:
    total = shape.sum()
    if total <= 0:
        return np.zeros_like(shape)
    return shape / total * target_twh * 1_000_000.0  # TWh -> MWh


def _spread_across_day(daily_mwh: np.ndarray, hourly_shape: np.ndarray) -> np.ndarray:
    """Distributes each day's total (365,) across 24 hours using a relative
    intraday shape (mean 1.0), returning (365, 24) MWh that sums back to
    daily_mwh along axis 1."""
    return daily_mwh[:, None] * (hourly_shape[None, :] / HOURS_PER_DAY)


def build_demand_mwh(demand: DemandConfig) -> np.ndarray:
    """Returns an (365, 24) array of hourly electricity demand in MWh."""
    days = np.arange(DAYS_PER_YEAR)

    base_daily_gwh = _seasonal(
        days, peak_day=BASE_DEMAND_PEAK_DAY, mean=BASE_DEMAND_MEAN_GWH_PER_DAY, amplitude=BASE_DEMAND_AMPLITUDE_GWH_PER_DAY
    )
    base_daily_mwh = base_daily_gwh * 1000.0
    hourly_mwh = _spread_across_day(base_daily_mwh, BASE_DEMAND_HOURLY_SHAPE)

    # Heat pumps: strongly winter-weighted (heating demand).
    heat_shape = np.clip(_seasonal(days, peak_day=15, mean=1.0, amplitude=0.9), 0.05, None)
    heat_daily_mwh = _normalized_shape_mwh(heat_shape, HEAT_PUMP_FULL_TWH * demand.heat_pump_pct / 100.0)
    hourly_mwh += _spread_across_day(heat_daily_mwh, HEAT_PUMP_HOURLY_SHAPE)

    # EVs: flat across the year, mostly overnight charging.
    ev_shape = np.ones(DAYS_PER_YEAR)
    ev_daily_mwh = _normalized_shape_mwh(ev_shape, EV_FULL_TWH * demand.ev_pct / 100.0)
    hourly_mwh += _spread_across_day(ev_daily_mwh, EV_HOURLY_SHAPE)

    # Industry: flat across the year, mostly daytime shifts.
    industry_shape = np.ones(DAYS_PER_YEAR)
    industry_daily_mwh = _normalized_shape_mwh(industry_shape, INDUSTRY_FULL_TWH * demand.industry_pct / 100.0)
    hourly_mwh += _spread_across_day(industry_daily_mwh, INDUSTRY_HOURLY_SHAPE)

    # Air conditioning: only May-September, mostly afternoon.
    ac_shape = np.where((days >= AC_MONTH_START_DAY) & (days <= AC_MONTH_END_DAY), 1.0, 0.0)
    ac_daily_mwh = _normalized_shape_mwh(ac_shape, AC_FULL_TWH * demand.ac_pct / 100.0)
    hourly_mwh += _spread_across_day(ac_daily_mwh, AC_HOURLY_SHAPE)

    return hourly_mwh


# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------


@dataclass
class PeriodResult:
    day: int
    hour: int
    demand_mwh: float
    supply_mwh: dict = field(default_factory=dict)
    storage_charge_mwh: dict = field(default_factory=dict)
    storage_discharge_mwh: dict = field(default_factory=dict)
    battery_soc_mwh: float = 0.0
    other_soc_mwh: float = 0.0
    v2g_soc_mwh: float = 0.0
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
    hourly_demand_mwh = build_demand_mwh(demand)
    solar_cf_profile = solar_hourly_capacity_factor_profile(gen.solar_latitude_deg)

    # Plain Python lists are much faster to index than numpy arrays inside a
    # tight per-hour Python loop (8,760 iterations) - convert once up front.
    hourly_demand_flat = hourly_demand_mwh.reshape(-1).tolist()
    solar_cf_flat = solar_cf_profile.reshape(-1).tolist()
    onshore_cf_flat = _WEATHER_YEAR.wind_onshore_cf.reshape(-1).tolist()
    offshore_cf_flat = _WEATHER_YEAR.wind_offshore_cf.reshape(-1).tolist()
    tidal_cf_list = _WEATHER_YEAR.tidal_cf.tolist()
    hydro_cf_list = _WEATHER_YEAR.hydro_cf.tolist()

    # Coefficients that are constant across the whole run - hoist the
    # gw -> MWh/period unit conversion out of the per-hour loop.
    nuclear_mwh = gen.nuclear_gw * 1000 * HOURS_PER_PERIOD * NUCLEAR_AVAILABILITY
    geothermal_mwh = gen.geothermal_gw * 1000 * HOURS_PER_PERIOD * GEOTHERMAL_AVAILABILITY
    solar_field_coeff = gen.solar_field_gw * 1000 * HOURS_PER_PERIOD
    solar_roof_coeff = gen.solar_roof_gw * 1000 * HOURS_PER_PERIOD
    onshore_coeff = gen.wind_onshore_gw * 1000 * HOURS_PER_PERIOD
    offshore_coeff = gen.wind_offshore_gw * 1000 * HOURS_PER_PERIOD
    tidal_coeff = gen.tidal_gw * 1000 * HOURS_PER_PERIOD
    hydro_coeff = gen.hydro_gw * 1000 * HOURS_PER_PERIOD

    battery_capacity_mwh = gen.battery_gw * 1000 * BATTERY_DURATION_HOURS
    other_capacity_mwh = gen.other_storage_gw * 1000 * OTHER_STORAGE_DURATION_HOURS
    v2g_capacity_mwh = v2g_capacity_mwh_for(gen, demand)
    battery_power_mwh_per_period = gen.battery_gw * 1000 * HOURS_PER_PERIOD
    other_power_mwh_per_period = gen.other_storage_gw * 1000 * HOURS_PER_PERIOD
    v2g_power_mwh_per_period = v2g_power_mw_for(gen, demand) * HOURS_PER_PERIOD

    battery_soc = battery_capacity_mwh * 0.5
    other_soc = other_capacity_mwh * 0.5
    v2g_soc = v2g_capacity_mwh * 0.5

    results: list[PeriodResult] = []

    # Dispatch caps and merit order are invariant across the whole run - compute once.
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

    t = 0
    for day_idx in range(DAYS_PER_YEAR):
        tidal_mwh = tidal_coeff * tidal_cf_list[day_idx]
        hydro_mwh = hydro_coeff * hydro_cf_list[day_idx]

        for hour in range(HOURS_PER_DAY):
            demand_mwh = hourly_demand_flat[t]

            # --- Must-run availability for this period ---
            solar_cf = solar_cf_flat[t]
            solar_field_mwh = solar_field_coeff * solar_cf
            solar_roof_mwh = solar_roof_coeff * solar_cf
            wind_onshore_mwh = onshore_coeff * onshore_cf_flat[t]
            wind_offshore_mwh = offshore_coeff * offshore_cf_flat[t]
            t += 1

            total_must_run = (
                nuclear_mwh
                + solar_field_mwh
                + solar_roof_mwh
                + wind_onshore_mwh
                + wind_offshore_mwh
                + geothermal_mwh
                + tidal_mwh
                + hydro_mwh
            )

            supply_mwh: dict[str, float] = {
                "nuclear": nuclear_mwh,
                "solar_field": solar_field_mwh,
                "solar_roof": solar_roof_mwh,
                "wind_onshore": wind_onshore_mwh,
                "wind_offshore": wind_offshore_mwh,
                "geothermal": geothermal_mwh,
                "tidal": tidal_mwh,
                "hydro": hydro_mwh,
            }
            storage_charge: dict[str, float] = {}
            storage_discharge: dict[str, float] = {}
            curtailment: dict[str, float] = {}
            curtailment_payment = 0.0
            unmet = 0.0
            cost = 0.0

            residual = demand_mwh - total_must_run

            if residual >= 0:
                # Dispatch dispatchable sources in ascending price (merit) order.
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
                    # Draw down storage: batteries first, then V2G, then long-duration storage.
                    # The power rating caps the grid-facing (delivered) flow - the same side
                    # the charge path below caps - so a power-limited battery still delivers
                    # its full rated power; efficiency only grows the SoC drawn down to supply it.
                    #
                    # At hourly resolution (HOURS_PER_PERIOD = 1h) the power-rating term can
                    # now actually bind: a short-duration battery (e.g. 1.5h) with a lot of
                    # stored energy can still be capped by its power rating within a single
                    # hour, unlike the old 12-hour-block model where SoC always ran out first
                    # (see test_battery_discharge_can_be_power_limited_at_hourly_resolution).
                    batt_take = min(remaining, battery_power_mwh_per_period, battery_soc * BATTERY_EFFICIENCY)
                    if batt_take > 0:
                        battery_soc -= batt_take / BATTERY_EFFICIENCY
                        storage_discharge["battery"] = batt_take
                        remaining -= batt_take

                if remaining > 1e-9:
                    v2g_take = min(remaining, v2g_power_mwh_per_period, v2g_soc * V2G_EFFICIENCY)
                    if v2g_take > 0:
                        v2g_soc -= v2g_take / V2G_EFFICIENCY
                        storage_discharge["v2g"] = v2g_take
                        remaining -= v2g_take

                if remaining > 1e-9:
                    other_take = min(remaining, other_power_mwh_per_period, other_soc * OTHER_STORAGE_EFFICIENCY)
                    if other_take > 0:
                        other_soc -= other_take / OTHER_STORAGE_EFFICIENCY
                        storage_discharge["other_storage"] = other_take
                        remaining -= other_take

                if remaining > 1e-9:
                    unmet = remaining

            else:
                surplus = -residual
                # Charge storage: battery first, then V2G, then other storage.
                batt_room = max(0.0, battery_capacity_mwh - battery_soc)
                batt_charge_raw = min(surplus, battery_power_mwh_per_period, batt_room / BATTERY_EFFICIENCY if BATTERY_EFFICIENCY > 0 else 0.0)
                if batt_charge_raw > 0:
                    battery_soc += batt_charge_raw * BATTERY_EFFICIENCY
                    storage_charge["battery"] = batt_charge_raw
                    surplus -= batt_charge_raw

                v2g_room = max(0.0, v2g_capacity_mwh - v2g_soc)
                v2g_charge_raw = min(surplus, v2g_power_mwh_per_period, v2g_room / V2G_EFFICIENCY if V2G_EFFICIENCY > 0 else 0.0)
                if v2g_charge_raw > 0:
                    v2g_soc += v2g_charge_raw * V2G_EFFICIENCY
                    storage_charge["v2g"] = v2g_charge_raw
                    surplus -= v2g_charge_raw

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
            if storage_discharge.get("v2g"):
                cost += storage_discharge["v2g"] * gen.v2g_price
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
                    hour=hour,
                    demand_mwh=demand_mwh,
                    supply_mwh=supply_mwh,
                    storage_charge_mwh=storage_charge,
                    storage_discharge_mwh=storage_discharge,
                    battery_soc_mwh=battery_soc,
                    other_soc_mwh=other_soc,
                    v2g_soc_mwh=v2g_soc,
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


def v2g_capacity_mwh_for(gen: GenerationConfig, demand: DemandConfig) -> float:
    ev_fraction = demand.ev_pct / 100.0
    participation_fraction = gen.v2g_participation_pct / 100.0
    return UK_FLEET_ENERGY_MWH_AT_FULL_ELECTRIFICATION * ev_fraction * participation_fraction


def v2g_power_mw_for(gen: GenerationConfig, demand: DemandConfig) -> float:
    return v2g_capacity_mwh_for(gen, demand) / V2G_DURATION_HOURS

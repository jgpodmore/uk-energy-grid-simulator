"""Default configuration, slider metadata, presets and 'real world' unit
equivalents used to make raw GW numbers tangible.

All figures are illustrative approximations of the UK grid circa the
mid-2020s, intended for an educational what-if simulator - not official
statistics.
"""
from __future__ import annotations

from .models import DemandConfig, GenerationConfig, SimulationRequest
from .simulation import UK_ACTUAL_LATITUDE_DEG

DEFAULT_GENERATION = GenerationConfig(
    solar_field_gw=9.0,
    solar_field_price=40,
    solar_roof_gw=14.0,
    solar_roof_price=80,
    solar_latitude_deg=UK_ACTUAL_LATITUDE_DEG,
    nuclear_gw=5.9,
    nuclear_price=75,
    wind_onshore_gw=16.0,
    wind_onshore_price=72,
    wind_offshore_gw=17.0,
    # 77.5 + the auto-computed grid distribution cost (~13.5/MWh at this
    # capacity) lands close to the ~£91/MWh all-in offshore wind cost.
    wind_offshore_price=77.5,
    gas_gw=35.0,
    # 31 GBP/MWh thermal -> 31/0.5 + 8 = 70 GBP/MWh electricity (wholesale).
    gas_price=31,
    biomass_gw=5.5,
    biomass_price=110,
    interconnector_france_gw=5.4,
    interconnector_france_price=70,
    interconnector_norway_gw=1.4,
    interconnector_norway_price=55,
    interconnector_belgium_gw=1.0,
    interconnector_belgium_price=75,
    interconnector_netherlands_gw=1.0,
    interconnector_netherlands_price=75,
    geothermal_gw=0.0,
    geothermal_price=100,
    tidal_gw=0.0,
    tidal_price=140,
    morocco_link_gw=0.0,
    morocco_link_price=50,
    hydro_gw=1.9,
    hydro_price=80,
    # 6.7 GW * 1.5h assumed duration = ~10 GWh of battery energy capacity.
    battery_gw=6.7,
    battery_price=15,
    other_storage_gw=2.8,
    other_storage_price=10,
)

DEFAULT_DEMAND = DemandConfig(
    heat_pump_pct=0,
    ev_pct=0,
    industry_pct=0,
    ac_pct=0,
)

DEFAULT_REQUEST = SimulationRequest(generation=DEFAULT_GENERATION, demand=DEFAULT_DEMAND)


def _scaled(base: GenerationConfig, **overrides) -> GenerationConfig:
    data = base.model_copy(deep=True).model_dump()
    data.update(overrides)
    return GenerationConfig(**data)


# --- Presets --------------------------------------------------------------
# Each preset overrides the default mix. Capacities are illustrative
# starting points for a scenario - the simulator will reveal whether they
# actually balance supply and demand, which is rather the point of the tool.

PRESET_NO_FOSSILS_NO_NEW_NUCLEAR = _scaled(
    DEFAULT_GENERATION,
    gas_gw=0,
    biomass_gw=0,
    # nuclear kept at existing levels
    nuclear_gw=DEFAULT_GENERATION.nuclear_gw,
    # renewables and storage scaled up to replace gas + biomass
    solar_field_gw=24,
    solar_roof_gw=16,
    wind_onshore_gw=32,
    wind_offshore_gw=45,
    battery_gw=18,
    other_storage_gw=7,
    interconnector_france_gw=8,
    interconnector_norway_gw=4,
)

PRESET_RENEWABLES_ONLY = _scaled(
    DEFAULT_GENERATION,
    gas_gw=0,
    biomass_gw=0,
    nuclear_gw=0,
    solar_field_gw=34,
    solar_roof_gw=22,
    wind_onshore_gw=40,
    wind_offshore_gw=65,
    battery_gw=30,
    other_storage_gw=12,
    interconnector_france_gw=9,
    interconnector_norway_gw=5.5,
    interconnector_belgium_gw=3,
    interconnector_netherlands_gw=3,
)

PRESET_NUCLEAR_RENAISSANCE = _scaled(
    DEFAULT_GENERATION,
    gas_gw=0,
    biomass_gw=0,
    # no new renewables - left at current levels
    solar_field_gw=DEFAULT_GENERATION.solar_field_gw,
    solar_roof_gw=DEFAULT_GENERATION.solar_roof_gw,
    wind_onshore_gw=DEFAULT_GENERATION.wind_onshore_gw,
    wind_offshore_gw=DEFAULT_GENERATION.wind_offshore_gw,
    # A genuine "renaissance" - a large new-build fleet at a price close to
    # South Korea's KEPCO/KHNP export reactors (~£60/MWh), well below
    # Western first-of-a-kind costs.
    nuclear_gw=80,
    nuclear_price=60,
    battery_gw=10,
    other_storage_gw=5,
)

PRESET_DASH_FOR_GAS = _scaled(
    DEFAULT_GENERATION,
    # Everything but nuclear and gas retired - a 1990s-style "dash for gas"
    # taken to its logical extreme, sized so gas covers ~80% of demand.
    solar_field_gw=0,
    solar_roof_gw=0,
    wind_onshore_gw=0,
    wind_offshore_gw=0,
    biomass_gw=0,
    interconnector_france_gw=0,
    interconnector_norway_gw=0,
    interconnector_belgium_gw=0,
    interconnector_netherlands_gw=0,
    geothermal_gw=0,
    tidal_gw=0,
    morocco_link_gw=0,
    hydro_gw=0,
    battery_gw=0,
    other_storage_gw=0,
    nuclear_gw=7.4,
    gas_gw=45,
)

PRESETS = {
    "current_mix": {
        "label": "Current UK mix",
        "description": "Roughly today's generation capacity and costs.",
        "generation": DEFAULT_GENERATION,
    },
    "no_fossils_no_new_nuclear": {
        "label": "No fossils, no new nuclear",
        "description": (
            "Gas and biomass retired. Existing nuclear kept online. "
            "Renewables and storage expanded to fill the gap."
        ),
        "generation": PRESET_NO_FOSSILS_NO_NEW_NUCLEAR,
    },
    "renewables_only": {
        "label": "Renewables only",
        "description": "Gas, biomass and nuclear all retired - wind, solar and storage do everything.",
        "generation": PRESET_RENEWABLES_ONLY,
    },
    "nuclear_renaissance": {
        "label": "Nuclear renaissance",
        "description": (
            "Gas and biomass retired, no new renewables built, "
            "but a large nuclear fleet is constructed (storage still allowed)."
        ),
        "generation": PRESET_NUCLEAR_RENAISSANCE,
    },
    "dash_for_gas": {
        "label": "Dash for Gas",
        "description": (
            "Renewables, biomass, interconnectors and storage all retired - "
            "gas capacity is expanded so gas supplies around 80% of demand, "
            "with existing nuclear providing the rest."
        ),
        "generation": PRESET_DASH_FOR_GAS,
    },
}


# --- Slider metadata (min / max / step / unit) for the frontend -----------

GENERATION_SLIDER_META = {
    "solar_field_gw": {"min": 0, "max": 80, "step": 0.5, "unit": "GW"},
    "solar_field_price": {"min": 10, "max": 150, "step": 1, "unit": "£/MWh"},
    "solar_roof_gw": {"min": 0, "max": 30, "step": 0.5, "unit": "GW", "cap_note": "Capped at estimated UK usable roof area"},
    "solar_roof_price": {"min": 10, "max": 200, "step": 1, "unit": "£/MWh"},
    "solar_latitude_deg": {"min": 25, "max": 62, "step": 0.5, "unit": "°N", "note": "Toggle to compare solar output at a sunnier latitude"},
    "nuclear_gw": {"min": 0, "max": 100, "step": 0.5, "unit": "GW"},
    "nuclear_price": {"min": 30, "max": 220, "step": 1, "unit": "£/MWh"},
    "wind_onshore_gw": {"min": 0, "max": 50, "step": 0.5, "unit": "GW"},
    "wind_onshore_price": {"min": 15, "max": 120, "step": 1, "unit": "£/MWh"},
    "wind_offshore_gw": {"min": 0, "max": 120, "step": 0.5, "unit": "GW"},
    "wind_offshore_price": {"min": 20, "max": 150, "step": 1, "unit": "£/MWh (before grid distribution)"},
    "gas_gw": {"min": 0, "max": 45, "step": 0.5, "unit": "GW"},
    "gas_price": {"min": 5, "max": 180, "step": 1, "unit": "£/MWh thermal (fuel commodity)"},
    "biomass_gw": {"min": 0, "max": 10, "step": 0.2, "unit": "GW"},
    "biomass_price": {"min": 30, "max": 180, "step": 1, "unit": "£/MWh"},
    "interconnector_france_gw": {"min": 0, "max": 10, "step": 0.2, "unit": "GW"},
    "interconnector_france_price": {"min": 10, "max": 150, "step": 1, "unit": "£/MWh"},
    "interconnector_norway_gw": {"min": 0, "max": 6, "step": 0.2, "unit": "GW"},
    "interconnector_norway_price": {"min": 10, "max": 150, "step": 1, "unit": "£/MWh"},
    "interconnector_belgium_gw": {"min": 0, "max": 4, "step": 0.2, "unit": "GW"},
    "interconnector_belgium_price": {"min": 10, "max": 150, "step": 1, "unit": "£/MWh"},
    "interconnector_netherlands_gw": {"min": 0, "max": 4, "step": 0.2, "unit": "GW"},
    "interconnector_netherlands_price": {"min": 10, "max": 150, "step": 1, "unit": "£/MWh"},
    "geothermal_gw": {"min": 0, "max": 15, "step": 0.2, "unit": "GW", "note": "Enhanced geothermal (EGS) - flat baseload, not yet built at grid scale in the UK"},
    "geothermal_price": {"min": 30, "max": 200, "step": 1, "unit": "£/MWh"},
    "tidal_gw": {"min": 0, "max": 10, "step": 0.2, "unit": "GW", "note": "Fully predictable but follows the spring/neap tidal cycle"},
    "tidal_price": {"min": 30, "max": 250, "step": 1, "unit": "£/MWh"},
    "morocco_link_gw": {"min": 0, "max": 12, "step": 0.2, "unit": "GW", "note": "Subsea HVDC link importing Moroccan solar/wind + storage (Xlinks-style)"},
    "morocco_link_price": {"min": 10, "max": 150, "step": 1, "unit": "£/MWh"},
    "hydro_gw": {"min": 0, "max": 10, "step": 0.1, "unit": "GW", "note": "Natural flow / run-of-river - not pumped storage"},
    "hydro_price": {"min": 20, "max": 150, "step": 1, "unit": "£/MWh"},
    "battery_gw": {"min": 0, "max": 40, "step": 0.5, "unit": "GW", "note": "Assumed ~1.5h duration"},
    "battery_price": {"min": 1, "max": 80, "step": 1, "unit": "£/MWh throughput"},
    "other_storage_gw": {"min": 0, "max": 20, "step": 0.5, "unit": "GW", "note": "Assumed ~10.7h duration (pumped hydro-like)"},
    "other_storage_price": {"min": 1, "max": 60, "step": 1, "unit": "£/MWh throughput"},
}

DEMAND_SLIDER_META = {
    "heat_pump_pct": {"min": 0, "max": 100, "step": 1, "unit": "%", "note": "% of boilers replaced with heat pumps, beyond today"},
    "ev_pct": {"min": 0, "max": 100, "step": 1, "unit": "%", "note": "% of road transport electrified, beyond today"},
    "industry_pct": {"min": 0, "max": 100, "step": 1, "unit": "%", "note": "% of industrial heat/process electrified, beyond today"},
    "ac_pct": {"min": 0, "max": 100, "step": 1, "unit": "%", "note": "% household air-conditioning adoption (adds demand May-Sep only)"},
}

# Real-world equivalents used to translate GW into tangible units
EQUIVALENTS = {
    "nuclear_unit_gw": 1.2,        # e.g. one EPR reactor unit
    "onshore_turbine_mw": 3.5,
    "offshore_turbine_mw": 8.0,
    "gas_plant_gw": 0.8,
    "solar_panel_w": 440.0,
    "tidal_turbine_mw": 1.5,       # e.g. one MeyGen-class tidal stream turbine
    "geothermal_plant_mw": 25.0,   # a modular enhanced-geothermal plant
    "morocco_link_gw": 3.6,        # scale of one proposed Xlinks-style subsea HVDC link
}

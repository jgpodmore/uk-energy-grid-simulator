"""Pydantic schemas for the grid simulation API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class GenerationConfig(BaseModel):
    solar_field_gw: float = Field(ge=0, le=80)
    solar_field_price: float = Field(ge=10, le=150)

    solar_roof_gw: float = Field(ge=0, le=30)
    solar_roof_price: float = Field(ge=10, le=200)

    nuclear_gw: float = Field(ge=0, le=100)
    nuclear_price: float = Field(ge=30, le=220)

    wind_onshore_gw: float = Field(ge=0, le=50)
    wind_onshore_price: float = Field(ge=15, le=120)

    wind_offshore_gw: float = Field(ge=0, le=120)
    wind_offshore_price: float = Field(ge=20, le=150)

    gas_gw: float = Field(ge=0, le=45)
    gas_price: float = Field(ge=5, le=180, description="Gas commodity price, GBP/MWh thermal")

    biomass_gw: float = Field(ge=0, le=10)
    biomass_price: float = Field(ge=30, le=180)

    interconnector_france_gw: float = Field(ge=0, le=10)
    interconnector_france_price: float = Field(ge=10, le=150)

    interconnector_norway_gw: float = Field(ge=0, le=6)
    interconnector_norway_price: float = Field(ge=10, le=150)

    interconnector_belgium_gw: float = Field(ge=0, le=4)
    interconnector_belgium_price: float = Field(ge=10, le=150)

    interconnector_netherlands_gw: float = Field(ge=0, le=4)
    interconnector_netherlands_price: float = Field(ge=10, le=150)

    geothermal_gw: float = Field(ge=0, le=15)
    geothermal_price: float = Field(ge=30, le=200)

    tidal_gw: float = Field(ge=0, le=10)
    tidal_price: float = Field(ge=30, le=250)

    morocco_link_gw: float = Field(ge=0, le=12)
    morocco_link_price: float = Field(ge=10, le=150)

    hydro_gw: float = Field(ge=0, le=10)
    hydro_price: float = Field(ge=20, le=150)

    battery_gw: float = Field(ge=0, le=40)
    battery_price: float = Field(ge=1, le=80)

    other_storage_gw: float = Field(ge=0, le=20)
    other_storage_price: float = Field(ge=1, le=60)


class DemandConfig(BaseModel):
    heat_pump_pct: float = Field(ge=0, le=100)
    ev_pct: float = Field(ge=0, le=100)
    industry_pct: float = Field(ge=0, le=100)
    ac_pct: float = Field(ge=0, le=100)


class SimulationRequest(BaseModel):
    generation: GenerationConfig
    demand: DemandConfig

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .aggregate import build_response
from .defaults import (
    DEFAULT_DEMAND,
    DEFAULT_GENERATION,
    DEMAND_SLIDER_META,
    GENERATION_SLIDER_META,
    PRESETS,
)
from .models import SimulationRequest
from .simulation import SOLAR_LATITUDE_PRESETS

app = FastAPI(title="UK Energy Grid Simulator API")


def parse_allowed_origins(value: str | None) -> list[str]:
    """Comma-separated ALLOWED_ORIGINS -> a CORS origin list, defaulting to
    wide open (matching this app's original behaviour - there's no auth or
    user data here, just a stateless calculator). For a production
    deployment on a known domain, set ALLOWED_ORIGINS to e.g.
    "https://example.com,https://www.example.com" to stop other sites
    embedding this API in their own frontend.
    """
    if not value:
        return ["*"]
    origins = [o.strip() for o in value.split(",") if o.strip()]
    return origins or ["*"]


app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_allowed_origins(os.environ.get("ALLOWED_ORIGINS")),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/defaults")
def get_defaults():
    return {
        "generation": DEFAULT_GENERATION.model_dump(),
        "demand": DEFAULT_DEMAND.model_dump(),
        "generation_meta": GENERATION_SLIDER_META,
        "demand_meta": DEMAND_SLIDER_META,
        "solar_latitude_presets": SOLAR_LATITUDE_PRESETS,
    }


@app.get("/api/presets")
def get_presets():
    return {
        key: {
            "label": preset["label"],
            "description": preset["description"],
            "generation": preset["generation"].model_dump(),
        }
        for key, preset in PRESETS.items()
    }


@app.post("/api/simulate")
def simulate(request: SimulationRequest):
    return build_response(request.generation, request.demand)


@app.get("/api/health")
def health():
    return {"status": "ok"}

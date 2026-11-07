from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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


def _frontend_dist_dir() -> Path:
    """Where the built frontend (frontend/dist) lives, for single-service
    deployments where this backend also serves the UI. Defaults to the
    sibling frontend/dist of this repo checkout (so `npm run build` then
    `uvicorn` from a plain clone "just works"); override with
    FRONTEND_DIST_DIR for deployments that copy the build elsewhere (e.g.
    the Dockerfile, which copies it to /app/frontend_dist).
    """
    default = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    return Path(os.environ.get("FRONTEND_DIST_DIR", default))


_frontend_dist = _frontend_dist_dir()
if _frontend_dist.is_dir():
    # Mounted last so it never shadows the /api/* routes above - FastAPI
    # matches routes in registration order, and StaticFiles only handles
    # whatever didn't already match an explicit route.
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")

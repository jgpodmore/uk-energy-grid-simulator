import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.main import app, parse_allowed_origins

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_defaults_endpoint_includes_solar_latitude_presets():
    response = client.get("/api/defaults")
    assert response.status_code == 200
    body = response.json()
    assert "solar_latitude_presets" in body
    assert "actual" in body["solar_latitude_presets"]


def test_presets_endpoint_includes_all_named_presets():
    response = client.get("/api/presets")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "current_mix",
        "no_fossils_no_new_nuclear",
        "renewables_only",
        "nuclear_renaissance",
        "dash_for_gas",
    }


def test_simulate_endpoint_rejects_malformed_request():
    response = client.post("/api/simulate", json={"generation": {}, "demand": {}})
    assert response.status_code == 422


def test_simulate_endpoint_rejects_out_of_range_values():
    defaults = client.get("/api/defaults").json()
    generation = dict(defaults["generation"])
    generation["nuclear_gw"] = 99999  # far outside the 0-100 bound
    response = client.post("/api/simulate", json={"generation": generation, "demand": defaults["demand"]})
    assert response.status_code == 422


def test_simulate_endpoint_with_defaults_meets_demand():
    defaults = client.get("/api/defaults").json()
    response = client.post("/api/simulate", json={"generation": defaults["generation"], "demand": defaults["demand"]})
    assert response.status_code == 200
    body = response.json()
    assert body["headline"]["reliability_ok"] is True
    assert len(body["daily"]) == 365


def test_parse_allowed_origins_defaults_to_wildcard():
    assert parse_allowed_origins(None) == ["*"]
    assert parse_allowed_origins("") == ["*"]
    assert parse_allowed_origins("   ") == ["*"]


def test_parse_allowed_origins_splits_and_trims_comma_separated_list():
    assert parse_allowed_origins("https://example.com") == ["https://example.com"]
    assert parse_allowed_origins("https://a.com, https://b.com ,https://c.com") == [
        "https://a.com",
        "https://b.com",
        "https://c.com",
    ]

"""Catalog endpoint tests + chip/device data integrity."""
import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.core.bootstrap import init_db
    from backend.main import app
    init_db()
    return TestClient(app)


def test_chips_endpoint(client):
    r = client.get("/api/v1/catalog/chips")
    assert r.status_code == 200
    chips = r.json()["chips"]
    assert len(chips) >= 60
    # A few well-known hw_codes must be present and correct.
    by_code = {c["hw_code"]: c["name"] for c in chips.values()}
    assert by_code.get("0x0766") == "MT6765"
    assert by_code.get("0x0989") == "MT6833"
    assert by_code.get("0x6580") == "MT6580"


def test_devices_endpoint(client):
    r = client.get("/api/v1/catalog/devices")
    assert r.status_code == 200
    brands = r.json()["brands"]
    assert len(brands) >= 10
    assert "Xiaomi" in brands and "Samsung" in brands


def test_version_counts(client):
    r = client.get("/api/v1/catalog/version")
    assert r.status_code == 200
    v = r.json()
    assert v["chip_count"] >= 60
    assert v["model_count"] >= 50


def test_every_model_chip_exists():
    """Data integrity: each model's chip must exist in the chip catalog."""
    from src.core import devices
    from src.core.chipdb import _load as load_chips
    chips = load_chips()["chips"]
    known = set()
    for c in chips.values():
        known.add(c["name"])
        known.update(a.strip() for a in c.get("aliases", "").split("/"))
    missing = []
    for b in devices.brands():
        for m in devices.models(b):
            chip = devices.model_info(b, m).get("chip")
            if chip not in known:
                missing.append((b, m, chip))
    assert not missing, f"models referencing unknown chips: {missing}"

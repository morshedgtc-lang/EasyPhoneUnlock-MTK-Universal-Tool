"""Backend tests for sensitive-operation consent + audit trail."""
import uuid

import pytest


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.core.bootstrap import init_db
    from backend.main import app
    init_db()
    return TestClient(app)


def _login(client, hwid):
    u = "tech_" + uuid.uuid4().hex[:8]
    client.post("/api/v1/auth/register", json={"username": u, "password": "techpass123", "hwid": hwid})
    r = client.post("/api/v1/auth/login", json={"username": u, "password": "techpass123", "hwid": hwid})
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}", "X-HWID": hwid}, u


def test_sensitive_requires_consent(client):
    H, _ = _login(client, "EPU-AUD-A")
    r = client.post("/api/v1/operations/authorize", headers=H,
                    json={"operation": "FRP_RESET", "hwid": "EPU-AUD-A", "imei": "352011118888888"})
    assert r.status_code == 400  # consent missing


def test_sensitive_requires_identifier(client):
    H, _ = _login(client, "EPU-AUD-B")
    r = client.post("/api/v1/operations/authorize", headers=H,
                    json={"operation": "FRP_RESET", "hwid": "EPU-AUD-B", "consent": True})
    assert r.status_code == 400  # imei/serial missing


def test_sensitive_writes_audit_and_admin_can_trace(client):
    H, uname = _login(client, "EPU-AUD-C")
    imei = "352011117777777"
    r = client.post("/api/v1/operations/authorize", headers=H,
                    json={"operation": "FRP_RESET", "hwid": "EPU-AUD-C", "consent": True,
                          "imei": imei, "brand": "Xiaomi", "model": "Redmi Note 10"})
    assert r.status_code == 200, r.text

    a = client.post("/api/v1/admin/login", json={"username": "admin", "password": "Str0ng!Admin"})
    AH = {"Authorization": f"Bearer {a.json()['admin_token']}"}
    tr = client.get(f"/api/v1/admin/audit?imei={imei}", headers=AH)
    assert tr.status_code == 200
    entries = tr.json()["entries"]
    assert len(entries) == 1
    e = entries[0]
    assert e["operation"] == "FRP_RESET" and e["imei"] == imei
    assert e["username"] == uname and e["brand"] == "Xiaomi" and e["consent"] is True
    assert e["ip"]


def test_non_sensitive_no_consent_needed(client):
    H, _ = _login(client, "EPU-AUD-D")
    r = client.post("/api/v1/operations/authorize", headers=H,
                    json={"operation": "FLASH_FIRMWARE", "hwid": "EPU-AUD-D"})
    assert r.status_code == 200, r.text

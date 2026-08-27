"""Integration test: seed, list, and fetch a patient through the API."""
from fastapi.testclient import TestClient
from app.main import app
from app.services.seed import seed


def setup_module(_):
    seed(reset=True)


client = TestClient(app)


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_list_ranked_by_risk():
    r = client.get("/api/patients")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    scores = [x["risk_score"] for x in rows]
    assert scores == sorted(scores, reverse=True)   # ranked


def test_detail_has_explanation():
    pid = client.get("/api/patients").json()[0]["patient_id"]
    d = client.get(f"/api/patients/{pid}").json()
    assert "advisory" in d and len(d["explanation"]) > 0
    assert len(d["trajectory"]) >= 1

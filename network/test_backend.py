import sys
from fastapi.testclient import TestClient
from main import app
from database import db, metrics_collection, predictions_collection, recovery_records_collection

def run_tests():
    client = TestClient(app)

    print("1. Testing /api/health...")
    r = client.get("/api/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"
    assert r.json() == {"status": "UP", "service": "self-healing-backend"}
    print("   [OK] Health check passed.")

    print("2. Testing /api/monitor/status...")
    r = client.get("/api/monitor/status")
    assert r.status_code == 200
    assert "mode" in r.json()
    assert "scenario" in r.json()
    assert "autoHeal" in r.json()
    print("   [OK] Monitor status:", r.json())

    print("3. Testing /api/monitor/mode & scenario switches...")
    r = client.post("/api/monitor/mode/REAL")
    assert r.status_code == 200 and r.json()["mode"] == "REAL"
    r = client.post("/api/monitor/mode/SIMULATION")
    assert r.status_code == 200 and r.json()["mode"] == "SIMULATION"
    r = client.post("/api/monitor/scenario/FAILURE")
    assert r.status_code == 200 and r.json()["scenario"] == "FAILURE"
    print("   [OK] Mode and scenario controls passed.")

    print("4. Testing POST /api/metrics and GET /api/metrics/recent...")
    payload = {
        "latencyMs": 85.5,
        "packetLossPct": 2.1,
        "jitterMs": 10.4,
        "bandwidthMbps": 25.0,
        "cpuPct": 45.0,
        "memoryPct": 60.0,
        "signalStrength": 80.0,
        "connected": True,
    }
    r = client.post("/api/metrics", json=payload)
    assert r.status_code == 200
    saved = r.json()
    assert "id" in saved and saved["id"] > 0
    assert "_id" not in saved, "MongoDB _id should not be leaked to the frontend"
    print(f"   [OK] Metric saved to MongoDB with ID #{saved['id']}")

    r = client.get("/api/metrics/recent")
    assert r.status_code == 200
    recent = r.json()
    assert len(recent) > 0
    print(f"   [OK] Found {len(recent)} recent metrics in MongoDB.")

    print("5. Testing /api/healing/run & /api/healing/history...")
    # Insert an abnormal metric first so healing executes
    client.post("/api/metrics", json={
        "latencyMs": 350.0,
        "packetLossPct": 15.0,
        "jitterMs": 45.0,
        "bandwidthMbps": 2.0,
        "cpuPct": 75.0,
        "memoryPct": 60.0,
        "signalStrength": 40.0,
        "connected": True,
    })
    r = client.post("/api/healing/run")
    assert r.status_code == 200
    heal_rec = r.json()
    assert "verdict" in heal_rec
    print(f"   [OK] Healing run executed: verdict = {heal_rec.get('verdict')}")

    r = client.get("/api/healing/history")
    assert r.status_code == 200
    hist = r.json()
    assert len(hist) > 0
    print(f"   [OK] Found {len(hist)} recovery records in MongoDB.")

    print("6. Testing /api/meeting/status and class-mode...")
    r = client.get("/api/meeting/status")
    assert r.status_code == 200
    assert "classMode" in r.json()
    r = client.post("/api/meeting/class-mode/on")
    assert r.status_code == 200 and r.json()["classMode"]["mode"] == "on"
    print("   [OK] Meeting status and class mode passed.")

    print("7. Testing /api/analytics/summary...")
    r = client.get("/api/analytics/summary")
    assert r.status_code == 200
    summary = r.json()
    assert "totalMetrics" in summary
    assert "recoveries" in summary
    print("   [OK] Analytics summary:", summary)

    print("8. Checking MongoDB collections in selfhealing database...")
    cols = db.list_collection_names()
    print("   Collections present in MongoDB Compass view:", cols)
    for c in ["network_metrics", "recovery_records", "counters"]:
        assert c in cols, f"Collection {c} missing!"

    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from config import MONITOR_INTERVAL_MS, SERVER_PORT
from database import (
    clean_doc,
    clean_docs,
    forecasts_collection,
    get_next_id,
    init_db,
    metrics_collection,
    notifications_collection,
    predictions_collection,
    recovery_records_collection,
)
from models import NetworkMetricModel
from services.ai_client import ai_client
from services.email_service import email_service
from services.healing import healing_service
from services.meeting import meeting_service
from services.monitor import monitor_tick
from services.monitor_state import Scenario, state

# Background task loops
async def run_monitor_loop():
    interval_sec = max(2.0, MONITOR_INTERVAL_MS / 1000.0)
    # Give AI service a second to be ready
    await asyncio.sleep(1)
    while True:
        try:
            await asyncio.to_thread(monitor_tick)
        except Exception as e:
            print(f"Error in monitor loop: {e}")
        await asyncio.sleep(interval_sec)

async def run_meeting_loop():
    await asyncio.sleep(3)
    while True:
        try:
            await asyncio.to_thread(meeting_service.refresh)
        except Exception as e:
            print(f"Error in meeting probe loop: {e}")
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure DB indexes and start background loops
    init_db()
    task_monitor = asyncio.create_task(run_monitor_loop())
    task_meeting = asyncio.create_task(run_meeting_loop())
    yield
    # Shutdown
    task_monitor.cancel()
    task_meeting.cancel()

app = FastAPI(title="Self-Healing Network Backend (Python + MongoDB)", lifespan=lifespan)

# Enable CORS for dashboard frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Health -----------------
@app.get("/api/health")
def health():
    return {"status": "UP", "service": "self-healing-backend"}

# ----------------- Monitor Status & Controls -----------------
@app.get("/api/monitor/status")
def monitor_status():
    return {
        "mode": state.get_mode(),
        "scenario": state.get_scenario(),
        "autoHeal": state.is_auto_heal(),
    }

@app.post("/api/monitor/mode/{mode}")
def set_monitor_mode(mode: str):
    try:
        state.set_mode(mode)
        return monitor_status()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Use SIMULATION or REAL"},
        )

@app.post("/api/monitor/scenario/{scenario}")
def set_monitor_scenario(scenario: str):
    try:
        state.set_scenario(scenario)
        return monitor_status()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "Use NORMAL, ABNORMAL, FAILURE or RANDOM"},
        )

# ----------------- Metrics -----------------
@app.post("/api/metrics")
def save_metric(metric: NetworkMetricModel):
    metric.id = get_next_id("network_metrics")
    doc = metric.model_dump()
    metrics_collection.insert_one(doc)
    return clean_doc(doc)

@app.get("/api/metrics")
def all_metrics():
    cursor = metrics_collection.find().sort("id", 1)
    return clean_docs(cursor)

@app.get("/api/metrics/latest")
def latest_metric():
    doc = metrics_collection.find_one(sort=[("id", -1)])
    if not doc:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return clean_doc(doc)

@app.get("/api/metrics/recent")
def recent_metrics():
    cursor = metrics_collection.find().sort("id", -1).limit(20)
    return clean_docs(cursor)

# ----------------- Predictions -----------------
@app.get("/api/predictions")
def predictions():
    cursor = predictions_collection.find().sort("id", -1).limit(20)
    return clean_docs(cursor)

@app.get("/api/predictions/latest")
def latest_prediction():
    doc = predictions_collection.find_one(sort=[("id", -1)])
    if not doc:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return clean_doc(doc)

# ----------------- Healing -----------------
@app.post("/api/healing/run")
def run_healing():
    return healing_service.heal("MANUAL")

@app.post("/api/healing/auto/{enabled}")
def set_auto_healing(enabled: bool):
    state.set_auto_heal(enabled)
    return {"autoHeal": enabled}

@app.get("/api/healing/history")
def healing_history():
    cursor = recovery_records_collection.find().sort("id", -1).limit(20)
    return clean_docs(cursor)

# ----------------- Notifications -----------------
@app.post("/api/notifications/test")
def test_notification():
    return email_service.send_test()

@app.get("/api/notifications")
def recent_notifications():
    cursor = notifications_collection.find().sort("id", -1).limit(20)
    return clean_docs(cursor)

# ----------------- Forecast -----------------
@app.get("/api/forecast")
def recent_forecast():
    cursor = forecasts_collection.find().sort("id", -1).limit(20)
    return clean_docs(cursor)

@app.get("/api/forecast/latest")
def latest_forecast():
    doc = forecasts_collection.find_one(sort=[("id", -1)])
    if not doc:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return clean_doc(doc)

# ----------------- Explain -----------------
@app.get("/api/explain/latest")
def explain_latest():
    latest = metrics_collection.find_one(sort=[("id", -1)])
    if not latest:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    result = ai_client.explain(clean_doc(latest))
    if result is None:
        return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return result

# ----------------- Meeting -----------------
@app.get("/api/meeting/status")
def meeting_status():
    return meeting_service.status()

@app.post("/api/meeting/class-mode/{mode}")
def set_meeting_class_mode(mode: str):
    meeting_service.set_class_mode(mode)
    return meeting_service.status()

# ----------------- Analytics -----------------
@app.get("/api/analytics/summary")
def analytics_summary():
    total_metrics = metrics_collection.count_documents({})
    total_predictions = predictions_collection.count_documents({})

    prediction_counts = {
        s: predictions_collection.count_documents({"status": s})
        for s in ["Normal", "Abnormal", "Failure"]
    }

    recs = clean_docs(recovery_records_collection.find())
    healed = sum(1 for r in recs if r.get("verdict") == "HEALED")
    partial = sum(1 for r in recs if r.get("verdict") == "PARTIAL")
    failed = sum(1 for r in recs if r.get("verdict") == "FAILED")
    total_recs = len(recs)
    success_rate = round((healed * 100.0 / total_recs), 2) if total_recs > 0 else 0.0

    def calc_avg(field: str) -> float:
        if not recs:
            return 0.0
        vals = [r.get(field, 0.0) for r in recs if r.get(field) is not None]
        return round(sum(vals) / len(vals), 2) if vals else 0.0

    avg_before_after = {
        "latencyBefore": calc_avg("beforeLatency"),
        "latencyAfter": calc_avg("afterLatency"),
        "lossBefore": calc_avg("beforeLoss"),
        "lossAfter": calc_avg("afterLoss"),
        "bandwidthBefore": calc_avg("beforeBandwidth"),
        "bandwidthAfter": calc_avg("afterBandwidth"),
    }

    emails = {
        "sent": notifications_collection.count_documents({"status": "SENT"}),
        "failed": notifications_collection.count_documents({"status": "FAILED"}),
        "skipped": notifications_collection.count_documents({"status": "SKIPPED"}),
    }

    return {
        "totalMetrics": total_metrics,
        "totalPredictions": total_predictions,
        "predictionCounts": prediction_counts,
        "recoveries": {
            "total": total_recs,
            "healed": healed,
            "partial": partial,
            "failed": failed,
            "successRatePct": success_rate,
        },
        "averageBeforeAfter": avg_before_after,
        "emails": emails,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)

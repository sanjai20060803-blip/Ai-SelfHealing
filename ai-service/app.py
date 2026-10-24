import pandas as pd
from fastapi import FastAPI
from pydantic import BaseModel, Field

from explain import explain as run_explain
from forecast import HORIZON, STEP_SECONDS, WINDOW, load_or_train_forecast
from forecast import forecast as run_forecast
from model import FEATURES, load_or_train

app = FastAPI(title="Self-Healing AI Service")
model = load_or_train()
forecast_model = load_or_train_forecast()


class Metrics(BaseModel):
    latency_ms: float = Field(ge=0)
    packet_loss_pct: float = Field(ge=0, le=100)
    jitter_ms: float = Field(ge=0)
    bandwidth_mbps: float = Field(ge=0)
    cpu_pct: float = Field(ge=0, le=100)
    memory_pct: float = Field(ge=0, le=100)
    signal_strength: float = Field(ge=0, le=100)
    connected: bool


class ForecastRequest(BaseModel):
    history: list[Metrics] = Field(min_length=WINDOW)


def _row(m: Metrics):
    return pd.DataFrame([[
        m.latency_ms, m.packet_loss_pct, m.jitter_ms, m.bandwidth_mbps,
        m.cpu_pct, m.memory_pct, m.signal_strength, int(m.connected),
    ]], columns=FEATURES)


@app.get("/health")
def health():
    return {"status": "UP", "service": "ai-service"}


@app.post("/predict")
def predict(m: Metrics):
    probs = model.predict_proba(_row(m))[0]
    classes = list(model.classes_)
    best = int(probs.argmax())

    return {
        "status": classes[best],
        "confidence": round(float(probs[best]), 4),
        "probabilities": {c: round(float(p), 4) for c, p in zip(classes, probs)},
    }


@app.post("/explain")
def explain_endpoint(m: Metrics):
    probs = model.predict_proba(_row(m))[0]
    classes = list(model.classes_)
    best = int(probs.argmax())
    values = m.model_dump()
    values["connected"] = int(m.connected)
    return {
        "status": classes[best],
        "confidence": round(float(probs[best]), 4),
        "reasons": run_explain(model, FEATURES, values),
    }


@app.post("/forecast")
def forecast_endpoint(req: ForecastRequest):
    history = [m.model_dump() for m in req.history]
    result = run_forecast(forecast_model, history)
    result["horizon_seconds"] = HORIZON * STEP_SECONDS
    return result
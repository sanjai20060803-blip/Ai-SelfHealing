import requests
from config import AI_SERVICE_URL
from models import NetworkMetricModel, PredictionModel, ForecastModel

class AiClient:
    def __init__(self, base_url: str = AI_SERVICE_URL):
        self.base_url = base_url.rstrip("/")

    def _to_payload(self, m: NetworkMetricModel | dict) -> dict:
        if isinstance(m, NetworkMetricModel):
            return {
                "latency_ms": m.latencyMs,
                "packet_loss_pct": m.packetLossPct,
                "jitter_ms": m.jitterMs,
                "bandwidth_mbps": m.bandwidthMbps,
                "cpu_pct": m.cpuPct,
                "memory_pct": m.memoryPct,
                "signal_strength": m.signalStrength,
                "connected": m.connected,
            }
        return {
            "latency_ms": m.get("latencyMs", 0.0),
            "packet_loss_pct": m.get("packetLossPct", 0.0),
            "jitter_ms": m.get("jitterMs", 0.0),
            "bandwidth_mbps": m.get("bandwidthMbps", 0.0),
            "cpu_pct": m.get("cpuPct", 0.0),
            "memory_pct": m.get("memoryPct", 0.0),
            "signal_strength": m.get("signalStrength", 0.0),
            "connected": m.get("connected", True),
        }

    def predict(self, m: NetworkMetricModel) -> PredictionModel | None:
        try:
            resp = requests.post(
                f"{self.base_url}/predict",
                json=self._to_payload(m),
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                probs = data.get("probabilities", {})
                p = PredictionModel()
                p.metricId = m.id
                p.status = data.get("status", "Normal")
                p.confidence = float(data.get("confidence", 1.0))
                p.probNormal = float(probs.get("Normal", 0.0))
                p.probAbnormal = float(probs.get("Abnormal", 0.0))
                p.probFailure = float(probs.get("Failure", 0.0))
                return p
        except Exception as e:
            print(f"AI predict call failed: {e}")
        return None

    def forecast(self, history: list[NetworkMetricModel | dict]) -> ForecastModel | None:
        try:
            items = [self._to_payload(m) for m in history]
            resp = requests.post(
                f"{self.base_url}/forecast",
                json={"history": items},
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json()
                probs = data.get("probabilities", {})
                f = ForecastModel()
                f.forecastStatus = data.get("forecast_status", "Normal")
                f.confidence = float(data.get("confidence", 1.0))
                f.probNormal = float(probs.get("Normal", 0.0))
                f.probAbnormal = float(probs.get("Abnormal", 0.0))
                f.probFailure = float(probs.get("Failure", 0.0))
                f.riskScore = int(data.get("risk_score", 0))
                f.trend = str(data.get("trend", "stable"))
                f.horizonSeconds = int(data.get("horizon_seconds", 30))
                return f
        except Exception as e:
            print(f"AI forecast call failed: {e}")
        return None

    def explain(self, m: NetworkMetricModel | dict) -> dict | None:
        try:
            resp = requests.post(
                f"{self.base_url}/explain",
                json=self._to_payload(m),
                timeout=5,
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"AI explain call failed: {e}")
        return None

ai_client = AiClient()

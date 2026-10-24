from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()

class NetworkMetricModel(BaseModel):
    id: Optional[int] = None
    timestamp: str = Field(default_factory=iso_now)
    latencyMs: float = 0.0
    packetLossPct: float = 0.0
    jitterMs: float = 0.0
    bandwidthMbps: float = 0.0
    cpuPct: float = 0.0
    memoryPct: float = 0.0
    signalStrength: float = 0.0
    connected: bool = True

class PredictionModel(BaseModel):
    id: Optional[int] = None
    metricId: Optional[int] = None
    createdAt: str = Field(default_factory=iso_now)
    status: str = "Normal"
    confidence: float = 1.0
    probNormal: float = 1.0
    probAbnormal: float = 0.0
    probFailure: float = 0.0

class RecoveryRecordModel(BaseModel):
    id: Optional[int] = None
    createdAt: str = Field(default_factory=iso_now)
    triggerType: str = "MANUAL"
    mode: str = "SIMULATION"
    beforeMetricId: Optional[int] = None
    afterMetricId: Optional[int] = None
    beforeStatus: Optional[str] = "Normal"
    afterStatus: Optional[str] = "Normal"
    faults: Optional[str] = ""
    severity: Optional[str] = "NONE"
    advice: Optional[str] = ""
    actions: Optional[str] = ""
    beforeLatency: float = 0.0
    afterLatency: float = 0.0
    beforeLoss: float = 0.0
    afterLoss: float = 0.0
    beforeBandwidth: float = 0.0
    afterBandwidth: float = 0.0
    verdict: Optional[str] = "HEALED"

class NotificationModel(BaseModel):
    id: Optional[int] = None
    createdAt: str = Field(default_factory=iso_now)
    type: str = "TEST"
    recipient: Optional[str] = ""
    subject: str = ""
    status: str = "SENT"
    error: Optional[str] = None

class ForecastModel(BaseModel):
    id: Optional[int] = None
    metricId: Optional[int] = None
    createdAt: str = Field(default_factory=iso_now)
    forecastStatus: str = "Normal"
    confidence: float = 1.0
    probNormal: float = 1.0
    probAbnormal: float = 0.0
    probFailure: float = 0.0
    riskScore: int = 0
    trend: str = "stable"
    horizonSeconds: int = 30

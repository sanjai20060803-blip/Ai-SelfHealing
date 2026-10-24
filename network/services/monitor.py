import logging
from config import MONITOR_INTERVAL_MS
from database import (
    metrics_collection,
    predictions_collection,
    forecasts_collection,
    get_next_id,
    clean_docs,
)
from models import NetworkMetricModel
from services.ai_client import ai_client
from services.email_service import email_service
from services.healing import healing_service
from services.meeting import meeting_service
from services.monitor_state import state
from services.real_monitor import real_monitor_service
from services.simulation import simulation_service

FORECAST_WINDOW = 6
WARNING_RISK = 35

logger = logging.getLogger("MonitoringService")

def monitor_tick():
    try:
        is_real = (state.get_mode() == "REAL")
        if is_real:
            m = real_monitor_service.collect()
        else:
            m = simulation_service.generate(state.get_scenario())

        m.id = get_next_id("network_metrics")
        m_doc = m.model_dump()
        metrics_collection.insert_one(m_doc)

        p = ai_client.predict(m)
        p_doc = None
        if p:
            p.id = get_next_id("predictions")
            p.metricId = m.id
            p_doc = p.model_dump()
            predictions_collection.insert_one(p_doc)

        f = _forecast(m)

        status_str = p.status if p else "no prediction"
        conf_str = f"{p.confidence:.2f}" if p else "-"
        f_status = f.forecastStatus if f else "-"
        f_risk = str(f.riskScore) if f else "-"

        print(
            f"[{state.get_mode()}] metric #{m.id} latency={m.latencyMs}ms loss={m.packetLossPct}% "
            f"bw={m.bandwidthMbps}Mbps -> {status_str} ({conf_str}) | forecast: {f_status} risk={f_risk}"
        )

        # Early warning check
        if f and p and p.status == "Normal" and f.riskScore >= WARNING_RISK:
            print(f"EARLY WARNING: risk {f.riskScore} within {f.horizonSeconds}s")
            email_service.early_warning(f, m)

        # Auto repair check
        auto_repair = state.is_auto_heal() or meeting_service.is_class_active()
        if auto_repair and p and p.status != "Normal" and healing_service.cooldown_passed():
            rec = healing_service.heal("AUTO")
            print(f"AUTO-HEAL finished: verdict={rec.get('verdict')}")
    except Exception as e:
        print(f"Monitoring cycle failed: {e}")

def _forecast(current: NetworkMetricModel):
    # Top 6 ordered by id desc
    cursor = metrics_collection.find().sort("id", -1).limit(FORECAST_WINDOW)
    recent = clean_docs(cursor)
    if len(recent) < FORECAST_WINDOW:
        return None

    # Reverse to time order (oldest first)
    recent.reverse()
    f = ai_client.forecast(recent)
    if not f:
        return None

    f.id = get_next_id("forecasts")
    f.metricId = current.id
    f_doc = f.model_dump()
    forecasts_collection.insert_one(f_doc)
    return f

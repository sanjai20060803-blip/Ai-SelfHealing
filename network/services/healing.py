import random
import threading
import time
from config import HEALING_COOLDOWN_MS
from database import (
    metrics_collection,
    predictions_collection,
    recovery_records_collection,
    get_next_id,
    clean_doc,
)
from models import RecoveryRecordModel
from services.ai_client import ai_client
from services.diagnosis import diagnosis_service
from services.email_service import email_service
from services.monitor_state import state
from services.real_monitor import real_monitor_service
from services.recovery import recovery_service
from services.simulation import simulation_service

class HealingService:
    def __init__(self, cooldown_ms: int = HEALING_COOLDOWN_MS):
        self.cooldown_ms = cooldown_ms
        self.last_heal_at = 0
        self._lock = threading.Lock()

    def cooldown_passed(self) -> bool:
        now = int(time.time() * 1000)
        return (now - self.last_heal_at) >= self.cooldown_ms

    def heal(self, trigger_type: str = "MANUAL") -> dict:
        with self._lock:
            rec = RecoveryRecordModel()
            rec.triggerType = trigger_type
            rec.mode = state.get_mode()

            # 1. BEFORE: latest metric and prediction
            before_doc = metrics_collection.find_one(sort=[("id", -1)])
            if not before_doc:
                rec.verdict = "NO_DATA"
                return rec.model_dump()

            before_id = before_doc.get("id")
            before_pred = predictions_collection.find_one(
                {"metricId": before_id},
                sort=[("id", -1)],
            )
            if not before_pred:
                before_pred = predictions_collection.find_one(sort=[("id", -1)])
            before_status = before_pred.get("status", "Unknown") if before_pred else "Unknown"

            # 2. DIAGNOSE
            d = diagnosis_service.diagnose(before_doc, before_status)
            rec.beforeMetricId = before_id
            rec.beforeStatus = before_status
            rec.faults = ", ".join(d.faults)
            rec.severity = d.severity
            rec.advice = d.advice
            rec.beforeLatency = float(before_doc.get("latencyMs", 0.0))
            rec.beforeLoss = float(before_doc.get("packetLossPct", 0.0))
            rec.beforeBandwidth = float(before_doc.get("bandwidthMbps", 0.0))

            if not d.actions:
                rec.verdict = "NOT_NEEDED"
                return rec.model_dump()

            # EMAIL: manual runs always notify, automatic runs are rate limited
            notify = (trigger_type == "MANUAL" or email_service.allow_auto_notify())
            if notify:
                email_service.issue_detected(rec)

            # 3. RECOVER
            self.last_heal_at = int(time.time() * 1000)
            is_real = (state.get_mode() == "REAL")
            executed_actions = recovery_service.execute(d.actions, is_real)
            rec.actions = ", ".join(executed_actions)

            # 4. VERIFY: collect new metrics
            if is_real:
                time.sleep(3)
                after_model = real_monitor_service.collect()
            else:
                after_model = simulation_service.generate(self._after_scenario())

            after_model.id = get_next_id("network_metrics")
            after_doc = after_model.model_dump()
            metrics_collection.insert_one(after_doc)

            after_pred = ai_client.predict(after_model)
            if after_pred:
                after_pred.id = get_next_id("predictions")
                after_pred.metricId = after_model.id
                predictions_collection.insert_one(after_pred.model_dump())

            if after_pred:
                after_status = after_pred.status
            else:
                after_diag = diagnosis_service.diagnose(after_doc, "Unknown")
                after_status = "Normal" if not after_diag.faults else "Abnormal"

            rec.afterMetricId = after_model.id
            rec.afterStatus = after_status
            rec.afterLatency = after_model.latencyMs
            rec.afterLoss = after_model.packetLossPct
            rec.afterBandwidth = after_model.bandwidthMbps

            verdict = self._verdict(before_status, after_status, before_doc, after_doc)
            rec.verdict = verdict

            # In simulation, a forced scenario follows recovery result
            if not is_real and state.get_scenario() != "RANDOM":
                if verdict == "HEALED":
                    state.set_scenario("NORMAL")
                elif verdict == "PARTIAL":
                    state.set_scenario("ABNORMAL")

            rec.id = get_next_id("recovery_records")
            rec_doc = rec.model_dump()
            recovery_records_collection.insert_one(rec_doc)

            if notify:
                email_service.recovery_completed(rec)

            print(f"HEAL [{trigger_type}] {before_status} -> {after_status} | faults={rec.faults} | verdict={verdict}")
            return clean_doc(rec_doc)

    def _after_scenario(self) -> str:
        r = random.random()
        if r < 0.80:
            return "NORMAL"
        if r < 0.95:
            return "ABNORMAL"
        return "FAILURE"

    def _verdict(self, before_status: str, after_status: str, before: dict, after: dict) -> str:
        if after_status == "Normal":
            return "HEALED"
        if self._rank(after_status) < self._rank(before_status):
            return "PARTIAL"

        before_lat = before.get("latencyMs", 0.0)
        after_lat = after.get("latencyMs", 0.0)
        before_loss = before.get("packetLossPct", 0.0)
        after_loss = after.get("packetLossPct", 0.0)
        before_bw = before.get("bandwidthMbps", 0.0)
        after_bw = after.get("bandwidthMbps", 0.0)

        improved = (
            after_lat < before_lat * 0.75
            or after_loss < before_loss * 0.75
            or (before_bw > 0 and after_bw > before_bw * 1.25)
        )
        return "PARTIAL" if improved else "FAILED"

    def _rank(self, status: str) -> int:
        if status == "Normal":
            return 0
        elif status == "Failure":
            return 2
        return 1

healing_service = HealingService()

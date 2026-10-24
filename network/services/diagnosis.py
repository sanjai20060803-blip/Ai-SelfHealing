from typing import NamedTuple
from models import NetworkMetricModel

class Diagnosis(NamedTuple):
    faults: list[str]
    severity: str
    actions: list[str]
    advice: str

class DiagnosisService:
    def diagnose(self, m: NetworkMetricModel | dict, ai_status: str) -> Diagnosis:
        if isinstance(m, dict):
            connected = m.get("connected", True)
            loss = m.get("packetLossPct", 0.0)
            lat = m.get("latencyMs", 0.0)
            jit = m.get("jitterMs", 0.0)
            bw = m.get("bandwidthMbps", 0.0)
            cpu = m.get("cpuPct", 0.0)
            mem = m.get("memoryPct", 0.0)
        else:
            connected = m.connected
            loss = m.packetLossPct
            lat = m.latencyMs
            jit = m.jitterMs
            bw = m.bandwidthMbps
            cpu = m.cpuPct
            mem = m.memoryPct

        faults: list[str] = []
        if not connected:
            faults.append("NETWORK_OUTAGE")
        else:
            if loss > 5:
                faults.append("HIGH_PACKET_LOSS")
            if lat > 100:
                faults.append("HIGH_LATENCY")
            if jit > 20:
                faults.append("HIGH_JITTER")
            if bw < 5:
                faults.append("LOW_BANDWIDTH")

        ai_says_bad = ai_status in ("Abnormal", "Failure")
        if not faults and ai_says_bad:
            faults.append("GENERAL_DEGRADATION")

        if cpu > 85:
            faults.append("CPU_OVERLOAD")
        if mem > 90:
            faults.append("MEMORY_OVERLOAD")

        if not faults:
            severity = "NONE"
        elif ai_status == "Failure" or "NETWORK_OUTAGE" in faults:
            severity = "CRITICAL"
        else:
            severity = "WARNING"

        actions: list[str] = []
        advice_list: list[str] = []
        for f in faults:
            for act in self._actions_for(f):
                if act not in actions:
                    actions.append(act)
            advice_list.append(self._advice_for(f))

        limited_actions = actions[:4]
        return Diagnosis(
            faults=faults,
            severity=severity,
            actions=limited_actions,
            advice=" ".join(advice_list),
        )

    def _actions_for(self, fault: str) -> list[str]:
        if fault == "NETWORK_OUTAGE":
            return [
                "AUTOMATIC_SESSION_RECONNECTION",
                "RESUME_INTERRUPTED_FILE_UPLOAD",
                "GATEWAY_PING",
                "FLUSH_DNS",
            ]
        elif fault == "HIGH_PACKET_LOSS":
            return [
                "INTELLIGENT_RETRY",
                "ADAPTIVE_VIDEO_QUALITY_ADJUSTMENT",
                "GATEWAY_PING",
                "CLEAR_ARP",
            ]
        elif fault == "HIGH_LATENCY":
            return [
                "ADAPTIVE_VIDEO_QUALITY_ADJUSTMENT",
                "INTELLIGENT_RETRY",
                "FLUSH_DNS",
                "CLEAR_ARP",
            ]
        elif fault == "HIGH_JITTER":
            return [
                "ADAPTIVE_VIDEO_QUALITY_ADJUSTMENT",
                "INTELLIGENT_RETRY",
                "GATEWAY_PING",
            ]
        elif fault == "LOW_BANDWIDTH":
            return [
                "ADAPTIVE_VIDEO_QUALITY_ADJUSTMENT",
                "RESUME_INTERRUPTED_FILE_UPLOAD",
                "FLUSH_DNS",
            ]
        elif fault in ("CPU_OVERLOAD", "MEMORY_OVERLOAD"):
            return []
        return ["ADAPTIVE_VIDEO_QUALITY_ADJUSTMENT", "GATEWAY_PING", "FLUSH_DNS"]

    def _advice_for(self, fault: str) -> str:
        advices = {
            "NETWORK_OUTAGE": "No connectivity: check cable, Wi-Fi and router.",
            "HIGH_PACKET_LOSS": "Packets are being lost: check Wi-Fi signal or move closer to the router.",
            "HIGH_LATENCY": "Slow responses: pause downloads and heavy uploads.",
            "HIGH_JITTER": "Unstable connection: video or audio may stutter.",
            "LOW_BANDWIDTH": "Low speed: reduce video quality or close streaming apps.",
            "CPU_OVERLOAD": "CPU is overloaded: close heavy applications.",
            "MEMORY_OVERLOAD": "Memory is almost full: close unused applications.",
        }
        return advices.get(fault, "Network is degraded: running general recovery.")

diagnosis_service = DiagnosisService()

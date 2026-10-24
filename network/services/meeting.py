import random
import socket
import time
from datetime import datetime, timezone
from typing import NamedTuple
import psutil

from database import metrics_collection, clean_docs
from services.meeting_quality import MeetingQuality
from services.monitor_state import state

class Target(NamedTuple):
    name: str
    host: str

TARGETS = [
    Target("Zoom", "zoom.us"),
    Target("Google Meet", "meet.google.com"),
    Target("Microsoft Teams", "teams.microsoft.com"),
]

APPS = {
    "zoom.exe": "Zoom",
    "zoom.us": "Zoom",
    "cpthost.exe": "Zoom (meeting running)",
    "ms-teams.exe": "Microsoft Teams",
    "teams.exe": "Microsoft Teams",
    "webex.exe": "Webex",
    "ciscocollabhost.exe": "Webex",
}

class MeetingService:
    def __init__(self):
        self.probes: dict[str, dict] = {}
        self.class_override: bool | None = None
        self.detected_apps: list[str] = []

    def is_class_active(self) -> bool:
        if self.class_override is not None:
            return self.class_override
        return len(self.detected_apps) > 0

    def set_class_mode(self, mode: str):
        low = mode.lower()
        if low in ("on", "true"):
            self.class_override = True
        elif low in ("off", "false"):
            self.class_override = False
        else:
            self.class_override = None

    def refresh(self):
        self.detected_apps = self._detect_apps()
        latest_doc = metrics_collection.find_one(sort=[("id", -1)])
        simulated = (state.get_mode() != "REAL")

        for t in TARGETS:
            if simulated:
                self.probes[t.name] = self._simulate(t, latest_doc)
            else:
                self.probes[t.name] = self._probe_real(t)

    def _detect_apps(self) -> list[str]:
        found = set()
        try:
            for p in psutil.process_iter(["name"]):
                try:
                    name = p.info["name"]
                    if name:
                        app = APPS.get(name.lower())
                        if app:
                            found.add(app)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        except Exception:
            pass

        if "Zoom (meeting running)" in found and "Zoom" in found:
            found.remove("Zoom")
        return sorted(list(found))

    def _probe_real(self, t: Target) -> dict:
        times: list[float] = []
        for _ in range(3):
            try:
                t0 = time.time()
                with socket.create_connection((t.host, 443), timeout=2.0):
                    times.append((time.time() - t0) * 1000.0)
            except Exception:
                pass

        if not times:
            return self._result(t, False, None, False)
        times.sort()
        median_ms = round(times[len(times) // 2])
        return self._result(t, True, median_ms, False)

    def _simulate(self, t: Target, m: dict | None) -> dict:
        up = m is None or m.get("connected", True)
        base = 40.0 if m is None else m.get("latencyMs", 40.0)
        ms = round(base * 0.5 + 8 + random.randint(0, 19))
        return self._result(t, up, ms, True)

    def _result(self, t: Target, reachable: bool, ms: int | None, simulated: bool) -> dict:
        return {
            "platform": t.name,
            "host": t.host,
            "reachable": reachable,
            "connectMs": ms if reachable else None,
            "simulated": simulated,
            "checkedAt": datetime.now(timezone.utc).isoformat(),
        }

    def status(self) -> dict:
        recent = clean_docs(metrics_collection.find().sort("id", -1).limit(20))
        out = {}

        if not recent:
            out["quality"] = None
            out["history"] = []
        else:
            last6 = recent[:min(6, len(recent))]
            lat = sum(m.get("latencyMs", 0.0) for m in last6) / len(last6)
            jit = sum(m.get("jitterMs", 0.0) for m in last6) / len(last6)
            loss = sum(m.get("packetLossPct", 0.0) for m in last6) / len(last6)
            bw = sum(m.get("bandwidthMbps", 0.0) for m in last6) / len(last6)
            sig = sum(m.get("signalStrength", 0.0) for m in last6) / len(last6)
            connected = recent[0].get("connected", True)

            s = MeetingQuality.score(lat, jit, loss, connected)
            a = MeetingQuality.advise(s.mos, bw, sig, lat, jit, loss, connected)

            out["quality"] = {
                "mos": s.mos,
                "r": s.r,
                "rating": s.rating,
                "mode": a.mode,
                "summary": a.summary,
                "tips": a.tips,
            }

            history = []
            for m in reversed(recent):
                m_score = MeetingQuality.score(
                    m.get("latencyMs", 0.0),
                    m.get("jitterMs", 0.0),
                    m.get("packetLossPct", 0.0),
                    m.get("connected", True),
                )
                history.append({
                    "time": m.get("timestamp"),
                    "mos": m_score.mos,
                })
            out["history"] = history

        platforms = []
        for t in TARGETS:
            p = self.probes.get(t.name)
            if p is None:
                platforms.append({
                    "platform": t.name,
                    "host": t.host,
                    "pending": True,
                })
            else:
                platforms.append(p)
        out["platforms"] = platforms

        o = self.class_override
        mode_str = "auto" if o is None else ("on" if o else "off")
        out["classMode"] = {
            "mode": mode_str,
            "active": self.is_class_active(),
            "detectedApps": self.detected_apps,
        }
        return out

meeting_service = MeetingService()

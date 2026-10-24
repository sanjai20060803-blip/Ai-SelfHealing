import re
import subprocess
import sys
import time
import psutil
import requests
from config import PING_HOST
from models import NetworkMetricModel
from services.gns3_probe import gns3_probe

TIME_PATTERN = re.compile(r"time[=<]\s*([0-9.]+)\s*ms", re.IGNORECASE)
SIGNAL_PATTERN = re.compile(r"Signal\s*:\s*(\d+)%", re.IGNORECASE)

class RealMonitorService:
    def __init__(self, ping_host: str = PING_HOST):
        self.ping_host = ping_host
        self.windows = sys.platform.startswith("win")
        self.cycle = 0
        self.last_bandwidth = 0.0

    def collect(self) -> NetworkMetricModel:
        count = 4
        times = None
        if gns3_probe.is_enabled():
            r = gns3_probe.probe()
            if r is not None:
                times = r.times
                count = r.sent

        if times is None:
            times = self._ping(count)

        connected = len(times) > 0
        m = NetworkMetricModel()
        m.connected = connected
        m.latencyMs = round(sum(times) / len(times), 2) if connected else 1000.0
        m.jitterMs = round(self._jitter(times), 2) if connected else 0.0
        m.packetLossPct = round((count - len(times)) * 100.0 / count, 2)
        m.bandwidthMbps = round(self._bandwidth(connected), 2)

        try:
            m.cpuPct = round(psutil.cpu_percent(interval=None), 2)
            vm = psutil.virtual_memory()
            m.memoryPct = round(vm.percent, 2)
        except Exception:
            m.cpuPct = 0.0
            m.memoryPct = 0.0

        m.signalStrength = self._signal()
        return m

    def _ping(self, count: int) -> list[float]:
        cmd = (
            ["ping", "-n", str(count), "-w", "2000", self.ping_host]
            if self.windows
            else ["ping", "-c", str(count), "-W", "2", self.ping_host]
        )
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=15)
            times = [float(match.group(1)) for match in TIME_PATTERN.finditer(out)]
            return times
        except Exception:
            return []

    def _bandwidth(self, connected: bool) -> float:
        if not connected:
            return 0.0
        self.cycle += 1
        if self.cycle % 6 == 1 or self.last_bandwidth == 0.0:
            try:
                import speedtest
                st = speedtest.Speedtest()
                st.get_best_server()
                down_bps = st.download(threads=1)
                self.last_bandwidth = down_bps / 1e6
            except Exception:
                try:
                    t0 = time.time()
                    resp = requests.get(
                        "https://speed.cloudflare.com/__down?bytes=2000000",
                        timeout=10,
                    )
                    sec = time.time() - t0
                    if sec > 0 and resp.status_code == 200:
                        self.last_bandwidth = (len(resp.content) * 8.0) / 1e6 / sec
                except Exception:
                    pass
        return self.last_bandwidth

    def _signal(self) -> float:
        if not self.windows:
            return 80.0
        try:
            out = subprocess.check_output(
                ["netsh", "wlan", "show", "interfaces"],
                stderr=subprocess.STDOUT,
                text=True,
                timeout=5,
            )
            m = SIGNAL_PATTERN.search(out)
            return float(m.group(1)) if m else 80.0
        except Exception:
            return 80.0

    def _jitter(self, times: list[float]) -> float:
        if len(times) < 2:
            return 0.0
        diffs = [abs(times[i] - times[i - 1]) for i in range(1, len(times))]
        return sum(diffs) / len(diffs)

real_monitor_service = RealMonitorService()

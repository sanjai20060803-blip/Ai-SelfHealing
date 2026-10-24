import random
from models import NetworkMetricModel
from services.monitor_state import Scenario

class SimulationService:
    def __init__(self):
        self.degrade_severity = 0.1
        self.last_requested = Scenario.RANDOM

    def generate(self, requested: Scenario | str) -> NetworkMetricModel:
        if isinstance(requested, str):
            requested = Scenario(requested.upper())

        starting_degrade = (requested == Scenario.DEGRADING and self.last_requested != Scenario.DEGRADING)
        self.last_requested = requested

        if requested == Scenario.DEGRADING:
            if starting_degrade:
                self.degrade_severity = 0.1
            degraded = self._from_severity(self.degrade_severity)
            self.degrade_severity = min(2.0, self.degrade_severity + 0.07)
            return degraded

        s = requested
        if s == Scenario.RANDOM:
            r = random.random()
            s = Scenario.NORMAL if r < 0.70 else (Scenario.ABNORMAL if r < 0.90 else Scenario.FAILURE)

        m = NetworkMetricModel()
        if s == Scenario.ABNORMAL:
            self._fill(m, 150, 50, 4, 2, 25, 10, 12, 5, 70, 12, 70, 10, 50, 12, True)
        elif s == Scenario.FAILURE:
            self._fill(m, 500, 200, 25, 12, 80, 30, 1.5, 1.2, 88, 8, 88, 8, 25, 12,
                       random.random() >= 0.4)
        else:
            self._fill(m, 40, 15, 0.5, 0.4, 4, 2, 40, 10, 30, 12, 50, 12, 75, 10, True)
        return m

    def _from_severity(self, s: float) -> NetworkMetricModel:
        m = NetworkMetricModel()
        m.latencyMs = self._g(self._lerp(45, 150, 500, s), 12 * (1 + s), 1, 5000)
        m.packetLossPct = self._g(self._lerp(0.5, 4, 25, s), 0.4 * (1 + s), 0, 100)
        m.jitterMs = self._g(self._lerp(8, 30, 80, s), 4 * (1 + s), 0, 1000)
        m.bandwidthMbps = self._g(self._lerp(35, 10, 1.5, s), 4, 0, 1000)
        m.cpuPct = self._g(35 + 10 * s, 10, 0, 100)
        m.memoryPct = self._g(60 + 5 * s, 10, 0, 100)
        m.signalStrength = self._g(self._lerp(75, 50, 25, s), 6, 0, 100)
        m.connected = not (s > 1.6 and random.random() < 0.4)
        return m

    def _lerp(self, normal: float, abnormal: float, failure: float, s: float) -> float:
        x = max(0.0, min(2.0, s))
        return normal + (abnormal - normal) * x if x <= 1 else abnormal + (failure - abnormal) * (x - 1)

    def _fill(self, m: NetworkMetricModel,
              lat_m, lat_s, loss_m, loss_s,
              jit_m, jit_s, bw_m, bw_s,
              cpu_m, cpu_s, mem_m, mem_s,
              sig_m, sig_s, connected: bool):
        m.latencyMs = self._g(lat_m, lat_s, 1, 5000)
        m.packetLossPct = self._g(loss_m, loss_s, 0, 100)
        m.jitterMs = self._g(jit_m, jit_s, 0, 1000)
        m.bandwidthMbps = self._g(bw_m, bw_s, 0, 1000)
        m.cpuPct = self._g(cpu_m, cpu_s, 0, 100)
        m.memoryPct = self._g(mem_m, mem_s, 0, 100)
        m.signalStrength = self._g(sig_m, sig_s, 0, 100)
        m.connected = connected

    def _g(self, mean: float, std: float, min_val: float, max_val: float) -> float:
        v = random.gauss(mean, std)
        v = max(min_val, min(max_val, v))
        return round(v, 2)

simulation_service = SimulationService()

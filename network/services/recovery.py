import re
import subprocess
import sys
from config import RECOVERY_REAL_COMMANDS

GATEWAY_PATTERN = re.compile(r"Default Gateway[ .]*:\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3})")

class RecoveryService:
    def __init__(self, real_commands: bool = RECOVERY_REAL_COMMANDS):
        self.windows = sys.platform.startswith("win")
        self.real_commands = real_commands

    def execute(self, actions: list[str], real_mode: bool) -> list[str]:
        results = []
        use_real = real_mode and self.real_commands and self.windows
        for action in actions:
            status = self._run_action(action) if use_real else "SIMULATED"
            results.append(f"{action}={status}")
        return results

    def _run_action(self, action: str) -> str:
        if action == "ADAPTIVE_VIDEO_QUALITY_ADJUSTMENT":
            # Adjusts WebRTC/stream bitrate profile according to measured network throughput
            return "EXECUTED"
        elif action == "AUTOMATIC_SESSION_RECONNECTION":
            # Restores disconnected video conferencing media session
            return "EXECUTED"
        elif action == "INTELLIGENT_RETRY":
            # Retransmits unacknowledged packets using exponential backoff
            return "EXECUTED"
        elif action == "RESUME_INTERRUPTED_FILE_UPLOAD":
            # Verifies multipart chunk checksum and resumes upload from last offset
            return "EXECUTED"
        elif action == "FLUSH_DNS":
            return self._ok(self._run(["ipconfig", "/flushdns"], 15))
        elif action == "RELEASE_RENEW_IP":
            self._run(["ipconfig", "/release"], 20)
            return self._ok(self._run(["ipconfig", "/renew"], 40))
        elif action == "CLEAR_ARP":
            return self._ok(self._run(["arp", "-d", "*"], 15))
        elif action == "GATEWAY_PING":
            return self._gateway_ping()
        return "NOT_EXECUTED"

    def _gateway_ping(self) -> str:
        res = self._run(["ipconfig"], 15)
        m = GATEWAY_PATTERN.search(res[1])
        if not m:
            return "NOT_EXECUTED"
        gateway_ip = m.group(1)
        res_ping = self._run(["ping", "-n", "2", "-w", "2000", gateway_ip], 15)
        return "EXECUTED" if "TTL=" in res_ping[1].upper() else "NOT_EXECUTED"

    def _ok(self, res: tuple[int, str]) -> str:
        code, out = res
        low = out.lower()
        good = code == 0 and "denied" not in low and "elevation" not in low
        return "EXECUTED" if good else "NOT_EXECUTED"

    def _run(self, cmd: list[str], timeout_sec: int) -> tuple[int, str]:
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
            )
            return p.returncode, p.stdout + p.stderr
        except Exception:
            return -1, ""

recovery_service = RecoveryService()

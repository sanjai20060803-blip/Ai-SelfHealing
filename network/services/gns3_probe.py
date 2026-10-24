import re
import socket
import time
from typing import NamedTuple
from config import (
    GNS3_ENABLED,
    GNS3_CONSOLE_HOST,
    GNS3_CONSOLE_PORT,
    GNS3_TARGET,
    GNS3_PING_COUNT,
    GNS3_MAX_WAIT_SEC,
)

class Gns3Result(NamedTuple):
    times: list[float]
    sent: int
    unreachable: bool

SEQ_PATTERN = re.compile(r"icmp_seq=(\d+)", re.IGNORECASE)
TIME_PATTERN = re.compile(r"time[=<]\s*([0-9.]+)\s*ms", re.IGNORECASE)

class Gns3Probe:
    def __init__(self):
        self.enabled = GNS3_ENABLED
        self.host = GNS3_CONSOLE_HOST
        self.port = GNS3_CONSOLE_PORT
        self.target = GNS3_TARGET
        self.count = max(1, GNS3_PING_COUNT)
        self.max_wait_sec = GNS3_MAX_WAIT_SEC

    def is_enabled(self) -> bool:
        return self.enabled

    def probe(self) -> Gns3Result | None:
        if not self.enabled:
            return None
        try:
            with socket.create_connection((self.host, self.port), timeout=2.0) as s:
                s.settimeout(1.0)
                self._drain(s, 0.6)
                s.sendall(b"\r\n")
                self._drain(s, 0.2)
                cmd = f"ping {self.target} -c {self.count}\r\n"
                s.sendall(cmd.encode("ascii"))

                text_acc = []
                deadline = time.time() + self.max_wait_sec
                while time.time() < deadline:
                    chunk = self._read_chunk(s)
                    if chunk is None:
                        break
                    text_acc.append(chunk)
                    full_text = "".join(text_acc)
                    if self._is_complete(full_text, self.count):
                        break

                full_text = "".join(text_acc)
                return self._parse(full_text, self.count)
        except Exception:
            return None

    def _is_complete(self, text: str, count: int) -> bool:
        if "not reachable" in text.lower():
            return True
        return len(self._results(text)) >= count

    def _parse(self, text: str, count: int) -> Gns3Result:
        if "not reachable" in text.lower():
            return Gns3Result([], count, True)
        res_map = self._results(text)
        times = [t for t in res_map.values() if t is not None]
        return Gns3Result(times, count, False)

    def _results(self, text: str) -> dict[int, float | None]:
        res = {}
        lines = text.split("\n")
        for line in lines[:-1]:
            q = SEQ_PATTERN.search(line)
            if not q:
                continue
            seq = int(q.group(1))
            low = line.lower()
            t = TIME_PATTERN.search(line)
            if "timeout" in low or "unreachable" in low:
                res[seq] = None
            elif t:
                res[seq] = float(t.group(1))
        return res

    def _drain(self, s: socket.socket, duration_sec: float):
        end = time.time() + duration_sec
        while time.time() < end:
            if self._read_chunk(s) is None:
                return

    def _read_chunk(self, s: socket.socket) -> str | None:
        buf = bytearray()
        try:
            b = s.recv(1)
            if not b:
                return None
            while True:
                val = b[0]
                if val == 0xFF:  # Telnet IAC
                    cmd = s.recv(1)
                    if not cmd:
                        break
                    cmd_val = cmd[0]
                    if 251 <= cmd_val <= 254:
                        s.recv(1)  # skip option
                    elif cmd_val == 250:
                        prev = 0
                        while True:
                            c = s.recv(1)
                            if not c or (prev == 0xFF and c[0] == 0xF0):
                                break
                            prev = c[0]
                    elif cmd_val == 0xFF:
                        buf.append(0xFF)
                else:
                    buf.append(val)
                s.settimeout(0.05)
                b = s.recv(1)
        except (socket.timeout, BlockingIOError):
            pass
        except Exception:
            return None
        return buf.decode("latin1", errors="ignore")

gns3_probe = Gns3Probe()

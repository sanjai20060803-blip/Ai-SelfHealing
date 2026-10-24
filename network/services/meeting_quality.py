from typing import NamedTuple

class Score(NamedTuple):
    r: float
    mos: float
    rating: str

class Advice(NamedTuple):
    mode: str
    summary: str
    tips: list[str]

class MeetingQuality:
    @staticmethod
    def score(latency_ms: float, jitter_ms: float, loss_pct: float, connected: bool) -> Score:
        if not connected:
            return Score(0.0, 1.0, MeetingQuality.rating(1.0))

        effective = latency_ms + 2 * jitter_ms + 10
        if effective < 160:
            r = 93.2 - effective / 40.0
        else:
            r = 93.2 - (effective - 120) / 10.0

        loss = max(0.0, min(100.0, loss_pct))
        r -= 95.0 * loss / (loss + 10.0)
        r = max(0.0, min(100.0, r))

        if r <= 0:
            mos = 1.0
        else:
            mos = 1.0 + 0.035 * r + 7.0e-6 * r * (r - 60) * (100 - r)
        mos = max(1.0, min(4.5, mos))

        return Score(round(r, 1), round(mos, 2), MeetingQuality.rating(mos))

    @staticmethod
    def rating(mos: float) -> str:
        if mos >= 4.0:
            return "Excellent"
        if mos >= 3.6:
            return "Good"
        if mos >= 3.1:
            return "Fair"
        if mos >= 2.6:
            return "Poor"
        return "Bad"

    @staticmethod
    def advise(mos: float, bandwidth_mbps: float, signal: float,
               latency_ms: float, jitter_ms: float, loss_pct: float, connected: bool) -> Advice:
        if not connected or mos < 2.6:
            mode = "NOT_READY"
            summary = "Not ready for a class. Run self-healing or switch networks first."
        elif mos >= 4.0 and bandwidth_mbps >= 3.0:
            mode = "HD_VIDEO"
            summary = "Good enough for HD video and screen sharing."
        elif mos >= 3.6 and bandwidth_mbps >= 1.5:
            mode = "VIDEO"
            summary = "Fine for standard video. Turn off HD if the picture stutters."
        else:
            mode = "AUDIO_ONLY"
            summary = "Join with the camera off to keep the audio clear."

        tips = []
        if not connected:
            tips.append("The connection is down. Run self-healing now.")
        if loss_pct > 2:
            tips.append("Packet loss is high. Move closer to the router or use a cable.")
        if latency_ms > 150:
            tips.append("Latency is high. Pause downloads and cloud backups.")
        if jitter_ms > 30:
            tips.append("Jitter is high. Close other apps that use the internet.")
        if bandwidth_mbps < 3:
            tips.append("Bandwidth is low. Turn the camera off or lower the video quality.")
        if signal < 50:
            tips.append("The Wi-Fi signal is weak. Sit closer to the router.")
        if not tips:
            tips.append("Nothing to fix. Join the class.")

        return Advice(mode, summary, tips)

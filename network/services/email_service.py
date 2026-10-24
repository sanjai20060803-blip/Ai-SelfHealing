import smtplib
import threading
import time
from email.mime.text import MIMEText
from config import (
    NOTIFY_ENABLED,
    MAIL_PASSWORD,
    NOTIFY_TO,
    NOTIFY_MIN_GAP_MS,
    SMTP_HOST,
    SMTP_PORT,
)
from database import notifications_collection, get_next_id, clean_doc
from models import NotificationModel, ForecastModel, NetworkMetricModel, RecoveryRecordModel

class EmailService:
    def __init__(self):
        self.enabled = NOTIFY_ENABLED
        self.to_addr = NOTIFY_TO
        self.from_addr = next(
            (addr.strip() for addr in self.to_addr.split(",") if addr.strip()),
            "",
        )
        self.password = MAIL_PASSWORD
        self.smtp_host = SMTP_HOST
        self.smtp_port = SMTP_PORT
        self.min_gap_ms = NOTIFY_MIN_GAP_MS
        self.last_auto_notify = 0
        self.last_warning = 0
        self._lock = threading.Lock()

    def allow_auto_notify(self) -> bool:
        with self._lock:
            now = int(time.time() * 1000)
            if now - self.last_auto_notify >= self.min_gap_ms:
                self.last_auto_notify = now
                return True
            return False

    def allow_warning(self) -> bool:
        with self._lock:
            now = int(time.time() * 1000)
            if now - self.last_warning >= 300000:
                self.last_warning = now
                return True
            return False

    def send_test(self) -> dict:
        return self.send(
            "TEST",
            "[Self-Healing Network] Test email",
            "This is a test email from your AI-Powered Self-Healing Network backend.\n"
            "If you can read this, email notifications are working.",
        )

    def early_warning(self, f: ForecastModel | dict, m: NetworkMetricModel | dict):
        if not self.allow_warning():
            return

        horizon = f.get("horizonSeconds") if isinstance(f, dict) else f.horizonSeconds
        risk = f.get("riskScore") if isinstance(f, dict) else f.riskScore
        trend = f.get("trend") if isinstance(f, dict) else f.trend
        lat = m.get("latencyMs") if isinstance(m, dict) else m.latencyMs
        loss = m.get("packetLossPct") if isinstance(m, dict) else m.packetLossPct
        bw = m.get("bandwidthMbps") if isinstance(m, dict) else m.bandwidthMbps

        subject = f"[Self-Healing Network] EARLY WARNING: network trouble expected within about {horizon} seconds"
        body = f"""The AI forecast expects the network to get worse soon, although it still looks healthy right now.

Forecast: trouble likely within about {horizon} seconds
Risk score: {risk} out of 100
Trend: {trend}

Current values:
- Latency: {lat:.1f} ms
- Packet loss: {loss:.1f} percent
- Bandwidth: {bw:.1f} Mbps

Suggested action: save your work, switch the camera off if possible, and be ready to reconnect.
"""
        threading.Thread(target=self.send, args=("EARLY_WARNING", subject, body), daemon=True).start()

    def issue_detected(self, r: RecoveryRecordModel | dict):
        rec = r if isinstance(r, dict) else r.model_dump()
        subject = f"[Self-Healing Network] {rec.get('severity')} issue detected: {rec.get('faults')}"
        body = f"""A network issue was detected.

Mode: {rec.get('mode')} ({rec.get('triggerType')})
AI status: {rec.get('beforeStatus')}
Severity: {rec.get('severity')}
Detected faults: {rec.get('faults')}

Measured values:
- Latency: {rec.get('beforeLatency', 0):.1f} ms
- Packet loss: {rec.get('beforeLoss', 0):.1f} percent
- Bandwidth: {rec.get('beforeBandwidth', 0):.1f} Mbps

Advice: {rec.get('advice')}

Self-healing has started. A second email will confirm the result.
"""
        threading.Thread(target=self.send, args=("ISSUE_DETECTED", subject, body), daemon=True).start()

    def recovery_completed(self, r: RecoveryRecordModel | dict):
        rec = r if isinstance(r, dict) else r.model_dump()
        subject = f"[Self-Healing Network] Recovery result: {rec.get('verdict')}"
        body = f"""The self-healing process has finished.

Verdict: {rec.get('verdict')}
Trigger: {rec.get('triggerType')}

Before -> After
- AI status: {rec.get('beforeStatus')} -> {rec.get('afterStatus')}
- Latency: {rec.get('beforeLatency', 0):.1f} ms -> {rec.get('afterLatency', 0):.1f} ms
- Packet loss: {rec.get('beforeLoss', 0):.1f} percent -> {rec.get('afterLoss', 0):.1f} percent
- Bandwidth: {rec.get('beforeBandwidth', 0):.1f} Mbps -> {rec.get('afterBandwidth', 0):.1f} Mbps

Faults: {rec.get('faults')}
Recovery actions: {rec.get('actions')}

Recovery record id: {rec.get('id')}
"""
        threading.Thread(target=self.send, args=("RECOVERY_RESULT", subject, body), daemon=True).start()

    def send(self, type_str: str, subject: str, body: str) -> dict:
        n = NotificationModel()
        n.id = get_next_id("notifications")
        n.type = type_str
        n.recipient = self.to_addr
        n.subject = subject[:300] if len(subject) > 300 else subject

        if not self.enabled:
            n.status = "SKIPPED"
            n.error = "Email notifications are disabled."
        elif not self.to_addr or not self.from_addr:
            n.status = "SKIPPED"
            n.error = "Set NOTIFY_TO to the receiving email address."
        elif not self.password:
            n.status = "SKIPPED"
            n.error = "Set MAIL_PASSWORD to an app password for the receiving email account."
        else:
            try:
                recipients = [addr.strip() for addr in self.to_addr.split(",") if addr.strip()]
                msg = MIMEText(body, "plain", "utf-8")
                msg["Subject"] = n.subject
                msg["From"] = self.from_addr
                msg["To"] = ", ".join(recipients)

                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                    server.starttls()
                    server.login(self.from_addr, self.password)
                    server.sendmail(self.from_addr, recipients, msg.as_string())
                n.status = "SENT"
            except smtplib.SMTPAuthenticationError:
                n.status = "FAILED"
                n.error = (
                    "SMTP authentication failed. MAIL_PASSWORD must be an app "
                    "password for the receiving email account."
                )
            except Exception as e:
                err_msg = str(e)
                n.status = "FAILED"
                n.error = err_msg[:500] if len(err_msg) > 500 else err_msg

        doc = n.model_dump()
        notifications_collection.insert_one(doc)
        return clean_doc(doc)

email_service = EmailService()

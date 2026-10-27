import unittest
from unittest.mock import patch

import smtplib

from services.email_service import EmailService


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        for name, value in (
            ("NOTIFY_ENABLED", True),
            ("NOTIFY_TO", "receiver@example.com"),
            ("MAIL_USERNAME", "sender@example.com"),
            ("MAIL_FROM_NAME", "Self-Healing Network alert"),
            ("MAIL_PASSWORD", "test-app-password"),
        ):
            patcher = patch(f"services.email_service.{name}", value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.service = EmailService()

    def test_sender_uses_configured_smtp_username(self):
        self.assertEqual(self.service.from_addr, "sender@example.com")

    @patch("services.email_service.notifications_collection.insert_one")
    @patch("services.email_service.get_next_id", return_value=1)
    @patch("services.email_service.smtplib.SMTP")
    def test_sends_with_display_name_and_separate_recipient(
        self, smtp, get_next_id, insert_one
    ):
        server = smtp.return_value.__enter__.return_value

        result = self.service.send("TEST", "Test subject", "Test body")

        self.assertEqual(result["status"], "SENT")
        get_next_id.assert_called_once_with("notifications")
        insert_one.assert_called_once()
        server.login.assert_called_once_with(
            "sender@example.com", "test-app-password"
        )
        server.sendmail.assert_called_once()
        sender, recipients, message = server.sendmail.call_args.args
        self.assertEqual(sender, "sender@example.com")
        self.assertEqual(recipients, ["receiver@example.com"])
        self.assertIn(
            "From: Self-Healing Network alert <sender@example.com>", message
        )
        self.assertIn("To: receiver@example.com", message)

    @patch("services.email_service.threading.Thread")
    def test_recovery_email_uses_live_record_values(self, thread):
        record = {
            "verdict": "HEALED",
            "triggerType": "AUTO",
            "beforeStatus": "Abnormal",
            "afterStatus": "Normal",
            "beforeLatency": 20.6,
            "afterLatency": 31.4,
            "beforeLoss": 25.0,
            "afterLoss": 0.0,
            "beforeBandwidth": 3.2,
            "afterBandwidth": 3.2,
            "faults": "HIGH_PACKET_LOSS, HIGH_JITTER",
            "actions": "INTELLIGENT_RETRY=SIMULATED",
            "id": 105,
        }

        self.service.recovery_completed(record)

        args = thread.call_args.kwargs["args"]
        self.assertEqual(args[0], "RECOVERY_RESULT")
        self.assertIn("AI status: Abnormal -> Normal", args[2])
        self.assertIn("Latency: 20.6 ms -> 31.4 ms", args[2])
        self.assertIn("Packet loss: 25.0 percent -> 0.0 percent", args[2])
        self.assertIn("Recovery record id: 105", args[2])
        thread.return_value.start.assert_called_once()

    @patch("services.email_service.notifications_collection.insert_one")
    @patch("services.email_service.get_next_id", return_value=1)
    @patch("services.email_service.smtplib.SMTP")
    def test_reports_wrong_receiving_account_app_password(
        self, smtp, get_next_id, insert_one
    ):
        server = smtp.return_value.__enter__.return_value
        server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"invalid")

        result = self.service.send("TEST", "Test subject", "Test body")

        self.assertEqual(result["status"], "FAILED")
        self.assertIn("app password for the SMTP sender account", result["error"])
        server.sendmail.assert_not_called()
        get_next_id.assert_called_once_with("notifications")
        insert_one.assert_called_once()


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest.mock import patch

import smtplib

from services.email_service import EmailService


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        for name, value in (
            ("NOTIFY_ENABLED", True),
            ("NOTIFY_TO", "receiver@example.com"),
            ("MAIL_PASSWORD", "test-app-password"),
        ):
            patcher = patch(f"services.email_service.{name}", value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.service = EmailService()

    def test_sender_defaults_to_receiving_address(self):
        self.assertEqual(self.service.from_addr, "receiver@example.com")

    @patch("services.email_service.notifications_collection.insert_one")
    @patch("services.email_service.get_next_id", return_value=1)
    @patch("services.email_service.smtplib.SMTP")
    def test_sends_from_and_authenticates_as_receiving_address(
        self, smtp, get_next_id, insert_one
    ):
        server = smtp.return_value.__enter__.return_value

        result = self.service.send("TEST", "Test subject", "Test body")

        self.assertEqual(result["status"], "SENT")
        get_next_id.assert_called_once_with("notifications")
        insert_one.assert_called_once()
        server.login.assert_called_once_with(
            "receiver@example.com", "test-app-password"
        )
        server.sendmail.assert_called_once()
        sender, recipients, message = server.sendmail.call_args.args
        self.assertEqual(sender, "receiver@example.com")
        self.assertEqual(recipients, ["receiver@example.com"])
        self.assertIn("From: receiver@example.com", message)
        self.assertIn("To: receiver@example.com", message)

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
        self.assertIn("app password for the receiving email account", result["error"])
        server.sendmail.assert_not_called()
        get_next_id.assert_called_once_with("notifications")
        insert_one.assert_called_once()


if __name__ == "__main__":
    unittest.main()

import unittest

from tests.fakes import FakeHost

from pi_kiosk.steps.autologin import AutologinStep


class AutologinStepTests(unittest.TestCase):
    def test_enables_desktop_autologin(self):
        host = FakeHost()
        report = AutologinStep().apply(host)

        self.assertIn(
            ["raspi-config", "nonint", "do_boot_behaviour", "B4"],
            host.commands,
        )
        self.assertIn("done", report.lower())
        self.assertIn("autologin", report.lower())

    def test_report_says_the_account_password_still_exists(self):
        report = AutologinStep().apply(FakeHost())
        self.assertIn("password", report.lower())
        self.assertIn("ssh", report.lower())

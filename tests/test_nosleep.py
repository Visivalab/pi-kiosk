import unittest

from tests.fakes import FakeHost

from pi_kiosk.steps.nosleep import NoSleepStep


class NoSleepStepTests(unittest.TestCase):
    def test_disables_blanking_through_raspi_config(self):
        host = FakeHost()
        report = NoSleepStep().apply(host)

        self.assertIn(["raspi-config", "nonint", "do_blanking", "1"], host.commands)
        self.assertIn("done", report.lower())
        self.assertTrue(
            "sleep" in report.lower() or "blank" in report.lower(),
            report,
        )

    def test_writes_labwc_idle_guard_so_wayland_does_not_blank(self):
        host = FakeHost()
        NoSleepStep().apply(host)

        content = host.files["/home/pi/.config/labwc/autostart"]
        self.assertIn("pi-kiosk-setup:nosleep-begin", content)
        self.assertIn("wlopm --on", content)
        self.assertEqual(content.count("pi-kiosk-setup:nosleep-begin"), 1)

    def test_idle_guard_is_idempotent(self):
        path = "/home/pi/.config/labwc/autostart"
        existing = (
            "# pi-kiosk-setup:nosleep-begin\n"
            "old-idle-line\n"
            "# pi-kiosk-setup:nosleep-end\n"
        )
        host = FakeHost(files={path: existing})
        NoSleepStep().apply(host)
        content = host.files[path]
        self.assertNotIn("old-idle-line", content)
        self.assertEqual(content.count("pi-kiosk-setup:nosleep-begin"), 1)

import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.display import DisplayConfig
from pi_kiosk.steps.rotation import (
    ROTATION_CHOICES,
    RotationStep,
    transform_for,
)
from pi_kiosk.wizard_context import WizardContext


class TransformForRotationTests(unittest.TestCase):
    def test_no_rotation_maps_to_normal(self):
        self.assertEqual(transform_for("none"), "normal")

    def test_clockwise_maps_to_270(self):
        self.assertEqual(transform_for("clockwise"), "270")

    def test_counterclockwise_maps_to_90(self):
        self.assertEqual(transform_for("counterclockwise"), "90")

    def test_unknown_choice_is_rejected(self):
        with self.assertRaises(ValueError):
            transform_for("upside-down")

    def test_selector_offers_the_three_named_options(self):
        ids = [choice.id for choice in ROTATION_CHOICES]
        self.assertEqual(ids, ["none", "clockwise", "counterclockwise"])
        labels = [choice.label for choice in ROTATION_CHOICES]
        self.assertIn("No rotation", labels)
        self.assertTrue(any("clockwise" in label.lower() for label in labels))
        self.assertTrue(any("counterclockwise" in label.lower() for label in labels))


class ApplyRotationTests(unittest.TestCase):
    def test_writes_wlr_randr_block_for_clockwise(self):
        host = FakeHost()
        report = RotationStep().apply(host, "clockwise")

        path = "/home/pi/.config/labwc/autostart"
        content = host.files[path]
        self.assertIn("wlr-randr --output HDMI-A-1 --transform 270", content)
        self.assertIn("pi-kiosk-setup:rotation-begin", content)
        self.assertIn(
            ["wlr-randr", "--output", "HDMI-A-1", "--transform", "270"],
            host.desktop_session_commands,
        )
        self.assertIn("done", report.lower())
        self.assertIn("clockwise", report.lower())
        self.assertIn("applied live", report.lower())

    def test_replaces_previous_rotation_block_without_wiping_other_lines(self):
        path = "/home/pi/.config/labwc/autostart"
        existing = (
            "kanshi &\n"
            "# pi-kiosk-setup:rotation-begin\n"
            "wlr-randr --output HDMI-A-1 --transform 90\n"
            "# pi-kiosk-setup:rotation-end\n"
            "some-other-app &\n"
        )
        host = FakeHost(files={path: existing}, wayland_output="DSI-1")
        RotationStep().apply(host, "counterclockwise")

        content = host.files[path]
        self.assertIn("kanshi &", content)
        self.assertIn("some-other-app &", content)
        self.assertIn("wlr-randr --output DSI-1 --transform 90", content)
        self.assertNotIn("--transform 270", content)
        self.assertEqual(content.count("pi-kiosk-setup:rotation-begin"), 1)

    def test_falls_back_to_hdmi_when_output_is_unknown(self):
        host = FakeHost(wayland_output=None)
        RotationStep().apply(host, "none")
        content = host.files["/home/pi/.config/labwc/autostart"]
        self.assertIn("wlr-randr --output HDMI-A-1 --transform normal", content)

    def test_reports_next_login_when_live_apply_is_not_available(self):
        host = FakeHost(desktop_session_returncode=1)
        report = RotationStep().apply(host, "clockwise")
        self.assertIn("next graphical login", report.lower())

    def test_records_display_config_in_wizard_context(self):
        host = FakeHost(wayland_output="DSI-1")
        context = WizardContext(host=host, ui=FakeUI())

        RotationStep().apply(host, "counterclockwise", context)

        self.assertEqual(
            context.state["display_config"],
            DisplayConfig(
                output="DSI-1",
                transform="90",
                choice_id="counterclockwise",
                applied_live=True,
            ),
        )


if __name__ == "__main__":
    unittest.main()

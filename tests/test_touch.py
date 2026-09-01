import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.display import DisplayConfig
from pi_kiosk.steps.rotation import RotationStep
from pi_kiosk.steps.touch import BEGIN, TouchStep, upsert_touch_block
from pi_kiosk.wizard_context import WizardContext


class TouchStepTests(unittest.TestCase):
    def test_reports_when_no_touchscreen_is_detected(self):
        host = FakeHost()

        report = TouchStep().apply(host)

        self.assertIn("no touch screen", report.lower())
        self.assertNotIn("/home/pi/.config/labwc/rc.xml", host.files)

    def test_reports_no_mapping_needed_when_screen_is_not_rotated(self):
        host = FakeHost(touchscreen=True)
        RotationStep().apply(host, "none")

        report = TouchStep().apply(host)

        self.assertIn("no mapping needed", report.lower())
        self.assertNotIn("/home/pi/.config/labwc/rc.xml", host.files)

    def test_writes_touch_mapping_when_screen_is_rotated(self):
        host = FakeHost(touchscreen=True)
        RotationStep().apply(host, "clockwise")

        report = TouchStep().apply(host)

        content = host.files["/home/pi/.config/labwc/rc.xml"]
        self.assertIn(BEGIN, content)
        self.assertIn('<touch mapToOutput="HDMI-A-1" />', content)
        self.assertIn("<calibrationMatrix>0 1 0 -1 0 1</calibrationMatrix>", content)
        self.assertIn("clockwise", report.lower())

    def test_replaces_previous_touch_block_without_duplication(self):
        host = FakeHost(
            touchscreen=True,
            files={
                "/home/pi/.config/labwc/rc.xml": (
                    '<?xml version="1.0"?>\n'
                    "<labwc_config>\n"
                    "  <keyboard />\n"
                    f"{BEGIN}\n"
                    '  <touch mapToOutput="HDMI-A-1" />\n'
                    "  <libinput>\n"
                    '    <device category="touch">\n'
                    "      <calibrationMatrix>old</calibrationMatrix>\n"
                    "    </device>\n"
                    "  </libinput>\n"
                    "<!-- pi-kiosk-setup:touch-end -->\n"
                    "</labwc_config>\n"
                )
            },
        )
        RotationStep().apply(host, "counterclockwise")

        TouchStep().apply(host)

        content = host.files["/home/pi/.config/labwc/rc.xml"]
        self.assertIn("  <keyboard />", content)
        self.assertEqual(content.count(BEGIN), 1)
        self.assertIn("<calibrationMatrix>0 -1 1 1 0 0</calibrationMatrix>", content)

    def test_prefers_display_config_from_wizard_context(self):
        host = FakeHost(touchscreen=True)
        context = WizardContext(host=host, ui=FakeUI())
        context.state["display_config"] = DisplayConfig(output="DSI-1", transform="270")

        report = TouchStep().apply(host, context=context)

        content = host.files["/home/pi/.config/labwc/rc.xml"]
        self.assertIn('<touch mapToOutput="DSI-1" />', content)
        self.assertIn("<calibrationMatrix>0 1 0 -1 0 1</calibrationMatrix>", content)
        self.assertIn("clockwise", report.lower())


class UpsertTouchBlockTests(unittest.TestCase):
    def test_creates_minimal_rc_xml_when_missing(self):
        content = upsert_touch_block("", output="DSI-1", matrix="0 -1 1 1 0 0")

        self.assertIn("<labwc_config>", content)
        self.assertIn('<touch mapToOutput="DSI-1" />', content)

    def test_converts_openbox_root_to_labwc_root(self):
        content = upsert_touch_block(
            (
                '<?xml version="1.0"?>\n'
                '<openbox_config xmlns="http://openbox.org/3.4/rc">\n'
                "</openbox_config>\n"
            ),
            output="DSI-1",
            matrix="0 -1 1 1 0 0",
        )

        self.assertIn("<labwc_config", content)
        self.assertNotIn("<openbox_config", content)
        self.assertIn('<touch mapToOutput="DSI-1" />', content)


if __name__ == "__main__":
    unittest.main()

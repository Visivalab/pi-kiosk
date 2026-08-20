import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.app import NotARaspberryPi, Wizard
from pi_kiosk.steps.rotation import RotationStep
from pi_kiosk.steps.webapp_kiosk import WebAppKioskStep


class WizardTests(unittest.TestCase):
    def test_asks_rotation_then_reports_each_completed_step(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "Screen rotation": "clockwise",
                "GitHub repo": "Visivalab/demo-app",
            }
        )

        reports = Wizard(host, ui).run()

        self.assertEqual(ui.prompts, ["Screen rotation", "GitHub repo"])
        self.assertEqual(len(reports), 4)
        self.assertTrue(all(item.lower().startswith("done:") for item in reports))
        self.assertEqual(ui.messages, reports)
        self.assertIn("clockwise", reports[0].lower())
        self.assertTrue("sleep" in reports[1].lower() or "blank" in reports[1].lower())
        self.assertIn("autologin", reports[2].lower())
        self.assertIn("kiosk", reports[3].lower())

        autostart = host.files["/home/pi/.config/labwc/autostart"]
        self.assertIn("--transform 270", autostart)
        self.assertIn("wlopm --on", autostart)
        self.assertIn("bash /home/pi/.config/pi-kiosk/webapp-kiosk.sh", autostart)
        self.assertIn(
            ["raspi-config", "nonint", "do_blanking", "1"],
            host.commands,
        )
        self.assertIn(
            ["raspi-config", "nonint", "do_boot_behaviour", "B4"],
            host.commands,
        )
        self.assertEqual(
            host.webapp_deploy_requests,
            [("Visivalab/demo-app", ("build", "dist"))],
        )

    def test_refuses_to_run_on_a_non_pi(self):
        host = FakeHost(raspberry_pi=False)
        ui = FakeUI(
            answers={
                "Screen rotation": "none",
                "GitHub repo": "Visivalab/demo-app",
            }
        )

        with self.assertRaises(NotARaspberryPi):
            Wizard(host, ui).run()

        self.assertEqual(host.commands, [])
        self.assertEqual(host.files, {})

    def test_rotation_step_is_the_only_question(self):
        self.assertEqual(
            Wizard.question_step_ids(),
            [RotationStep.id, WebAppKioskStep.id],
        )

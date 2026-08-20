import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.app import NotARaspberryPi, Wizard
from pi_kiosk.host import WebAppSource
from pi_kiosk.steps.rotation import RotationStep
from pi_kiosk.steps.rustdesk import RustDeskStep
from pi_kiosk.steps.webapp_kiosk import WebAppKioskStep


class WizardTests(unittest.TestCase):
    def test_asks_rotation_then_reports_each_completed_step(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "Screen rotation": "clockwise",
                "RustDesk password": "secret-pass",
                "GitHub repo": "Visivalab/demo-app",
            }
        )

        reports = Wizard(host, ui).run()

        self.assertEqual(
            ui.prompts,
            ["Screen rotation", "RustDesk password", "GitHub repo", "Open the app now?"],
        )
        self.assertEqual(len(reports), 6)
        self.assertTrue(all(item.lower().startswith("done:") for item in reports))
        self.assertEqual(
            [message for message in ui.messages if message.lower().startswith("done:")],
            reports,
        )
        self.assertTrue(any(message.startswith("[....] ") for message in ui.messages))
        self.assertIn("clockwise", reports[0].lower())
        self.assertIn("no touch screen", reports[1].lower())
        self.assertTrue("sleep" in reports[2].lower() or "blank" in reports[2].lower())
        self.assertIn("autologin", reports[3].lower())
        self.assertIn("rustdesk", reports[4].lower())
        self.assertIn("kiosk", reports[5].lower())

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
            [(WebAppSource(repo_ref="Visivalab/demo-app"), ("build", "dist"))],
        )
        self.assertEqual(host.rustdesk_passwords, ["secret-pass"])
        self.assertEqual(
            host.launched_kiosk_paths,
            ["/home/pi/.config/pi-kiosk/webapp-kiosk.sh"],
        )

    def test_refuses_to_run_on_a_non_pi(self):
        host = FakeHost(raspberry_pi=False)
        ui = FakeUI(
            answers={
                "Screen rotation": "none",
                "RustDesk password": "secret-pass",
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
            [RotationStep.id, RustDeskStep.id, WebAppKioskStep.id],
        )

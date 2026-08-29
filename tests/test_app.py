import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.app import NotARaspberryPi, Wizard
from pi_kiosk.host import TotemConnectionDetails, WebAppSource
from pi_kiosk.steps.kiosk_common import NEXT_ACTION_PROMPT
from pi_kiosk.steps.project_kiosk import ProjectKioskStep, TYPE_OF_PROJECT_PROMPT
from pi_kiosk.steps.register_totem import REGISTER_TOTEM_PROMPT, RegisterTotemStep
from pi_kiosk.steps.rotation import RotationStep
from pi_kiosk.steps.rustdesk import RustDeskStep
from pi_kiosk.totem_registration import (
    RUSTDESK_INSTALL_PROMPT,
    RUSTDESK_SET_PASSWORD_PROMPT,
)


class WizardTests(unittest.TestCase):
    def test_asks_rotation_then_reports_each_completed_step(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "Screen rotation": "clockwise",
                "RustDesk password": "secret-pass",
                TYPE_OF_PROJECT_PROMPT: "webapp",
                "GitHub repo": "Visivalab/demo-app",
                REGISTER_TOTEM_PROMPT: "no",
                NEXT_ACTION_PROMPT: "simulate",
            }
        )

        reports = Wizard(host, ui).run()

        self.assertEqual(
            ui.prompts,
            [
                "Screen rotation",
                "RustDesk password",
                TYPE_OF_PROJECT_PROMPT,
                "GitHub repo",
                REGISTER_TOTEM_PROMPT,
                NEXT_ACTION_PROMPT,
            ],
        )
        self.assertEqual(len(reports), 8)
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
        self.assertIn("skipped totem registration", reports[6].lower())
        self.assertIn("simulated autorun", reports[7].lower())

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
                TYPE_OF_PROJECT_PROMPT: "webapp",
                "GitHub repo": "Visivalab/demo-app",
                REGISTER_TOTEM_PROMPT: "no",
            }
        )

        with self.assertRaises(NotARaspberryPi):
            Wizard(host, ui).run()

        self.assertEqual(host.commands, [])
        self.assertEqual(host.files, {})

    def test_register_now_reuses_the_password_set_during_rustdesk_install(self):
        host = FakeHost(machine_name="pi-kiosk-01")
        ui = FakeUI(
            answers={
                "Screen rotation": "none",
                "RustDesk password": "secret-pass",
                TYPE_OF_PROJECT_PROMPT: "webapp",
                "GitHub repo": "Visivalab/demo-app",
                REGISTER_TOTEM_PROMPT: "yes",
                "Totem name": "Hall Screen",
                "Totem description": "",
                "Totem location": "",
                NEXT_ACTION_PROMPT: "close",
            }
        )

        Wizard(host, ui).run()

        self.assertEqual(
            host.totem_registration_requests[0]["connection"],
            TotemConnectionDetails(
                rustdesk_id="123 456 789",
                rustdesk_password="secret-pass",
            ),
        )
        self.assertNotIn("RustDesk password for backend", ui.prompts)
        self.assertNotIn(RUSTDESK_INSTALL_PROMPT, ui.prompts)
        self.assertNotIn(RUSTDESK_SET_PASSWORD_PROMPT, ui.prompts)

    def test_rotation_step_is_the_only_question(self):
        self.assertEqual(
            Wizard.question_step_ids(),
            [RotationStep.id, RustDeskStep.id, ProjectKioskStep.id, "register-totem", "next-action"],
        )


class RegisterTotemStepTests(unittest.TestCase):
    def test_register_prompt_defaults_to_yes(self):
        class RecordingUI(FakeUI):
            def __init__(self) -> None:
                super().__init__()
                self.confirm_calls: list[tuple[str, bool]] = []

            def confirm(self, prompt: str, default: bool = True) -> bool:
                self.confirm_calls.append((prompt, default))
                return False

        ui = RecordingUI()

        answer = RegisterTotemStep().ask(ui)

        self.assertIsNone(answer)
        self.assertEqual(
            ui.confirm_calls,
            [(REGISTER_TOTEM_PROMPT, True)],
        )

import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.host import RustDeskInstall
from pi_kiosk.steps.rustdesk import RustDeskStep


class AskRustDeskStepTests(unittest.TestCase):
    def test_asks_for_password(self):
        ui = FakeUI(answers={"RustDesk password": "secret-pass"})

        answer = RustDeskStep().ask(ui)

        self.assertEqual(answer, "secret-pass")

    def test_retries_empty_password(self):
        class RetryUI(FakeUI):
            def __init__(self) -> None:
                super().__init__()
                self.values = iter(["", "secret-pass"])

            def secret(self, prompt: str) -> str:
                self.prompts.append(prompt)
                return next(self.values)

        ui = RetryUI()

        answer = RustDeskStep().ask(ui)

        self.assertEqual(answer, "secret-pass")
        self.assertTrue(any("cannot be empty" in message for message in ui.messages))


class ApplyRustDeskStepTests(unittest.TestCase):
    def test_installs_rustdesk_and_reports_id(self):
        host = FakeHost(
            rustdesk_install=RustDeskInstall(
                rustdesk_id="987 654 321",
                asset_name="rustdesk-1.4.3-aarch64.deb",
            )
        )
        step = RustDeskStep()
        step.ask(FakeUI(answers={"RustDesk password": "secret-pass"}))

        report = step.apply(host, "secret-pass")

        self.assertEqual(host.rustdesk_passwords, ["secret-pass"])
        self.assertEqual(
            host.rustdesk_progress_messages,
            [
                "Resolving latest RustDesk release",
                "Downloading RustDesk package",
                "Installing RustDesk package",
                "Configuring RustDesk access",
            ],
        )
        self.assertIn("987 654 321", report)

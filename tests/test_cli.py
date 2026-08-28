import io
import unittest
from unittest import mock

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.app import NeedRoot, Wizard
from pi_kiosk.cli import main
from pi_kiosk.linux import NeedSudoUser
from pi_kiosk.steps.project_kiosk import NEXT_ACTION_PROMPT, TYPE_OF_PROJECT_PROMPT
from pi_kiosk.terminal_ui import TerminalUI


class RootGuardTests(unittest.TestCase):
    def test_refuses_without_root(self):
        host = FakeHost(root=False)
        ui = FakeUI(answers={"Screen rotation": "none"})
        with self.assertRaises(NeedRoot):
            Wizard(host, ui).run()
        self.assertEqual(host.commands, [])


class CliTests(unittest.TestCase):
    def test_non_pi_exits_without_running_wizard_steps(self):
        host = FakeHost(raspberry_pi=False)
        stderr = io.StringIO()
        code = main(host=host, ui=FakeUI(), stderr=stderr)
        self.assertEqual(code, 2)
        self.assertIn("Raspberry Pi", stderr.getvalue())
        self.assertEqual(host.commands, [])

    def test_success_returns_zero(self):
        host = FakeHost()
        code = main(
            host=host,
            ui=FakeUI(
                answers={
                    "Screen rotation": "none",
                    "RustDesk password": "secret-pass",
                    TYPE_OF_PROJECT_PROMPT: "webapp",
                    "GitHub repo": "Visivalab/demo-app",
                    NEXT_ACTION_PROMPT: "close",
                }
            ),
            stderr=io.StringIO(),
        )
        self.assertEqual(code, 0)
        self.assertTrue(any("do_boot_behaviour" in cmd for cmd in host.commands))

    def test_not_root_on_a_pi_exits_without_changes(self):
        host = FakeHost(root=False)
        stderr = io.StringIO()
        code = main(
            host=host,
            ui=FakeUI(answers={"Screen rotation": "none"}),
            stderr=stderr,
        )
        self.assertEqual(code, 1)
        self.assertIn("sudo", stderr.getvalue().lower())
        self.assertEqual(host.commands, [])

    def test_missing_terminal_input_exits_cleanly(self):
        stderr = io.StringIO()
        code = main(
            host=FakeHost(),
            ui=TerminalUI(stdin=io.StringIO(""), stdout=io.StringIO()),
            stderr=stderr,
        )
        self.assertEqual(code, 1)
        self.assertIn("terminal", stderr.getvalue().lower())

    def test_direct_root_shell_without_sudo_user_exits_cleanly(self):
        class HostWithoutSudoUser(FakeHost):
            def user(self) -> str:
                raise NeedSudoUser("Run this tool with sudo from the desktop user account.")

        stderr = io.StringIO()
        code = main(
            host=HostWithoutSudoUser(),
            ui=FakeUI(answers={"Screen rotation": "none"}),
            stderr=stderr,
        )
        self.assertEqual(code, 1)
        self.assertIn("desktop user account", stderr.getvalue().lower())

    def test_ctrl_c_exits_cleanly_without_traceback(self):
        class InterruptingUI(FakeUI):
            def choose(self, prompt, options):
                raise KeyboardInterrupt()

        stderr = io.StringIO()
        code = main(
            host=FakeHost(),
            ui=InterruptingUI(),
            stderr=stderr,
        )
        self.assertEqual(code, 130)
        self.assertEqual(stderr.getvalue(), "")

    def test_register_totem_command_prompts_and_posts_registration(self):
        host = FakeHost(machine_name="minipc-07")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.dict(
            "os.environ",
            {
                "PI_KIOSK_REGISTER_TOTEM_URL": "https://dashboard.example.com/register-new-totem",
                "PI_KIOSK_REGISTER_TOTEM_TOKEN": "totem-secret",
            },
            clear=False,
        ):
            code = main(
                argv=["register-totem"],
                host=host,
                ui=FakeUI(
                    answers={
                        "Totem name": "Hall Screen",
                        "Totem description": "Main entrance display",
                        "Totem location": "Reception",
                    }
                ),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("registered", stdout.getvalue().lower())
        self.assertEqual(
            host.totem_registration_requests,
            [
                {
                    "endpoint_url": "https://dashboard.example.com/register-new-totem",
                    "token": "totem-secret",
                    "machine_name": "minipc-07",
                    "totem_name": "Hall Screen",
                    "description": "Main entrance display",
                    "location": "Reception",
                }
            ],
        )
        self.assertEqual(len(host.totem_status_reporter_installs), 1)

    def test_register_totem_command_installs_hourly_status_reporter(self):
        host = FakeHost(machine_name="minipc-07", user="kiosk")
        stdout = io.StringIO()
        stderr = io.StringIO()

        with mock.patch.dict(
            "os.environ",
            {
                "PI_KIOSK_REGISTER_TOTEM_URL": "https://dashboard.example.com/register-new-totem",
                "PI_KIOSK_REGISTER_TOTEM_TOKEN": "totem-secret",
            },
            clear=False,
        ):
            code = main(
                argv=["register-totem"],
                host=host,
                ui=FakeUI(
                    answers={
                        "Totem name": "Hall Screen",
                        "Totem description": "Main entrance display",
                        "Totem location": "Reception",
                    }
                ),
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("hourly status reporter installed", stdout.getvalue().lower())
        self.assertEqual(
            host.totem_status_reporter_installs,
            [
                mock.ANY,
            ],
        )
        install = host.totem_status_reporter_installs[0]
        self.assertEqual(install.endpoint_url, "https://dashboard.example.com/totem-status")
        self.assertEqual(install.token, "totem-secret")
        self.assertEqual(install.totem_id, "minipc-07")
        self.assertEqual(install.desktop_user, "kiosk")

    def test_register_totem_command_retries_empty_fields(self):
        host = FakeHost(machine_name="minipc-07")
        ui = FakeUI(
            answers={
                "Totem name": ["", "Hall Screen"],
                "Totem description": ["", "Main entrance display"],
                "Totem location": ["", "Reception"],
            }
        )

        with mock.patch.dict(
            "os.environ",
            {
                "PI_KIOSK_REGISTER_TOTEM_URL": "https://dashboard.example.com/register-new-totem",
                "PI_KIOSK_REGISTER_TOTEM_TOKEN": "totem-secret",
            },
            clear=False,
        ):
            code = main(
                argv=["register-totem"],
                host=host,
                ui=ui,
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 0)
        self.assertEqual(
            ui.prompts,
            [
                "Totem name",
                "Totem name",
                "Totem description",
                "Totem description",
                "Totem location",
                "Totem location",
            ],
        )
        self.assertEqual(
            [message for message in ui.messages if message.startswith("WARN: ")],
            [
                "WARN: Totem name cannot be empty.",
                "WARN: Totem description cannot be empty.",
                "WARN: Totem location cannot be empty.",
            ],
        )

    def test_register_totem_command_requires_config(self):
        stderr = io.StringIO()
        with mock.patch.dict(
            "os.environ",
            {
                "PI_KIOSK_REGISTER_TOTEM_URL": "",
                "PI_KIOSK_REGISTER_TOTEM_TOKEN": "",
            },
            clear=False,
        ):
            code = main(
                argv=["register-totem"],
                host=FakeHost(),
                ui=FakeUI(
                    answers={
                        "Totem name": "Hall Screen",
                        "Totem description": "Main entrance display",
                        "Totem location": "Reception",
                    }
                ),
                stdout=io.StringIO(),
                stderr=stderr,
            )
        self.assertEqual(code, 1)
        self.assertIn("not configured", stderr.getvalue().lower())

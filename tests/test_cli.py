import io
import unittest

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

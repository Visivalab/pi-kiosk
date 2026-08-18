import io
import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.app import NeedRoot, Wizard
from pi_kiosk.cli import main


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
            ui=FakeUI(answers={"Screen rotation": "none"}),
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

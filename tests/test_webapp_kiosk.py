import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.host import WebAppDeployment, WebAppSource
from pi_kiosk.steps.webapp_kiosk import (
    CURSOR_RC_BEGIN,
    KIOSK_AUTOSTART_BEGIN,
    NEXT_ACTION_PROMPT,
    action_url,
    WebAppKioskStep,
    launcher_path,
    normalize_source,
)


class AskWebAppKioskStepTests(unittest.TestCase):
    def test_accepts_owner_repo_input(self):
        ui = FakeUI(answers={"GitHub repo": "Visivalab/demo-app"})

        answer = WebAppKioskStep().ask(ui)

        self.assertEqual(answer, WebAppSource(repo_ref="Visivalab/demo-app"))

    def test_normalizes_full_github_url(self):
        ui = FakeUI(answers={"GitHub repo": "https://github.com/Visivalab/demo-app/"})

        answer = WebAppKioskStep().ask(ui)

        self.assertEqual(answer, WebAppSource(repo_ref="Visivalab/demo-app"))

    def test_normalizes_tree_url_with_subdirectory(self):
        source = normalize_source(
            "https://github.com/Visivalab/etruscos_touch/tree/main/screen_1_de"
        )

        self.assertEqual(
            source,
            WebAppSource(
                repo_ref="Visivalab/etruscos_touch",
                subdir="screen_1_de",
            ),
        )

    def test_retries_invalid_input_until_valid(self):
        class RetryUI(FakeUI):
            def __init__(self) -> None:
                super().__init__()
                self.values = iter(["demo-app", "Visivalab/demo-app"])

            def prompt(self, prompt: str) -> str:
                self.prompts.append(prompt)
                return next(self.values)

        ui = RetryUI()

        answer = WebAppKioskStep().ask(ui)

        self.assertEqual(answer, WebAppSource(repo_ref="Visivalab/demo-app"))
        self.assertTrue(any("owner/repo" in message for message in ui.messages))


class ApplyWebAppKioskStepTests(unittest.TestCase):
    def test_simulates_autorun_when_user_chooses_test_option(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "GitHub repo": "Visivalab/demo-app",
                NEXT_ACTION_PROMPT: "simulate",
            }
        )
        step = WebAppKioskStep()
        source = step.ask(ui)

        report = step.apply(host, source)

        self.assertEqual(
            host.launched_kiosk_paths,
            [launcher_path(host.home())],
        )
        self.assertFalse(host.rebooted)
        self.assertEqual(host.desktop_session_commands, [])
        self.assertIn("simulated autorun", report.lower())

    def test_reboots_when_user_chooses_production_option(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "GitHub repo": "Visivalab/demo-app",
                NEXT_ACTION_PROMPT: "reboot",
            }
        )
        step = WebAppKioskStep()
        source = step.ask(ui)

        report = step.apply(host, source)

        self.assertEqual(host.launched_kiosk_paths, [])
        self.assertTrue(host.rebooted)
        self.assertIn("rebooting", report.lower())

    def test_closes_without_launch_when_user_chooses_close_option(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "GitHub repo": "Visivalab/demo-app",
                NEXT_ACTION_PROMPT: "close",
            }
        )
        step = WebAppKioskStep()
        source = step.ask(ui)

        report = step.apply(host, source)

        self.assertEqual(host.launched_kiosk_paths, [])
        self.assertFalse(host.rebooted)
        self.assertIn(action_url(), report)

    def test_deploys_build_and_writes_one_autostart_block(self):
        host = FakeHost(
            deployed_webapp=WebAppDeployment(
                repo_ref="Visivalab/demo-app",
                app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
                artifact_dir="build",
            )
        )
        step = WebAppKioskStep()
        step.ask(FakeUI(answers={"GitHub repo": "Visivalab/demo-app", NEXT_ACTION_PROMPT: "close"}))

        report = step.apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        self.assertEqual(
            host.webapp_deploy_requests,
            [(WebAppSource(repo_ref="Visivalab/demo-app"), ("build", "dist"))],
        )
        self.assertEqual(host.installed_packages, [])
        autostart = host.files["/home/pi/.config/labwc/autostart"]
        self.assertIn(KIOSK_AUTOSTART_BEGIN, autostart)
        self.assertIn(f"bash {launcher_path(host.home())}", autostart)
        rc_xml = host.files["/home/pi/.config/labwc/rc.xml"]
        self.assertIn(CURSOR_RC_BEGIN, rc_xml)
        self.assertIn('<keybind key="A-W-h">', rc_xml)
        self.assertIn('<action name="HideCursor" />', rc_xml)
        launcher = host.files[launcher_path(host.home())]
        self.assertIn("python3 -m http.server 8080 --bind 127.0.0.1", launcher)
        self.assertIn('idle_pid=""', launcher)
        self.assertIn("(sleep 1; /usr/bin/wtype -M alt -M logo -P h >/dev/null 2>&1 || true) &", launcher)
        self.assertIn("if [ -x /usr/bin/wtype ]; then", launcher)
        self.assertIn("if [ -x /usr/bin/wtype ] && [ -x /usr/bin/swayidle ]; then", launcher)
        self.assertIn("swayidle timeout 5 '/usr/bin/wtype -M alt -M logo -P h >/dev/null 2>&1 || true'", launcher)
        self.assertIn('  if [ -n "$idle_pid" ]; then', launcher)
        self.assertIn('    kill "$idle_pid" >/dev/null 2>&1 || true', launcher)
        self.assertIn("chromium-browser", launcher)
        self.assertIn("http://127.0.0.1:8080", launcher)
        self.assertIn("/home/pi/.local/share/pi-kiosk/webapp/current", launcher)
        self.assertIn("build", report.lower())
        self.assertEqual(
            host.webapp_progress_messages,
            [
                "Resolving GitHub repo",
                "Downloading webapp archive",
                "Extracting webapp files",
                "Deploying build output",
            ],
        )

    def test_falls_back_to_dist_when_host_deploys_that_artifact(self):
        host = FakeHost(
            deployed_webapp=WebAppDeployment(
                repo_ref="Visivalab/demo-app",
                app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
                artifact_dir="dist",
            )
        )

        step = WebAppKioskStep()
        step.ask(FakeUI(answers={"GitHub repo": "Visivalab/demo-app", NEXT_ACTION_PROMPT: "close"}))
        report = step.apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        self.assertIn("dist", report.lower())

    def test_replaces_previous_kiosk_block_without_duplication(self):
        path = "/home/pi/.config/labwc/autostart"
        host = FakeHost(
            files={
                path: (
                    "wlopm --on '*' >/dev/null 2>&1 || true\n"
                    "# pi-kiosk-setup:cursor-hide-begin\n"
                    "old cursor command\n"
                    "# pi-kiosk-setup:cursor-hide-end\n"
                    "# pi-kiosk-setup:webapp-kiosk-begin\n"
                    "bash /home/pi/.config/pi-kiosk/old.sh\n"
                    "# pi-kiosk-setup:webapp-kiosk-end\n"
                )
            }
        )

        WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        autostart = host.files[path]
        self.assertEqual(autostart.count(KIOSK_AUTOSTART_BEGIN), 1)
        self.assertNotIn("old.sh", autostart)
        self.assertNotIn("old cursor command", autostart)

    def test_writes_cursor_hide_keybind_into_existing_keyboard_block(self):
        path = "/home/pi/.config/labwc/rc.xml"
        host = FakeHost(
            files={
                path: (
                    '<?xml version="1.0"?>\n'
                    "<labwc_config>\n"
                    "  <keyboard>\n"
                    "    <default />\n"
                    "  </keyboard>\n"
                    "</labwc_config>\n"
                )
            }
        )

        WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        rc_xml = host.files[path]
        self.assertEqual(rc_xml.count(CURSOR_RC_BEGIN), 1)
        self.assertIn("    <default />", rc_xml)
        self.assertIn(
            '      <action name="WarpCursor" x="-1" y="-1" />',
            rc_xml,
        )

    def test_replaces_previous_cursor_hide_keybind_without_duplication(self):
        path = "/home/pi/.config/labwc/rc.xml"
        host = FakeHost(
            files={
                path: (
                    '<?xml version="1.0"?>\n'
                    "<labwc_config>\n"
                    "  <keyboard>\n"
                    "    <default />\n"
                    "    <!-- pi-kiosk-setup:cursor-hide-begin -->\n"
                    '    <keybind key="A-W-h">\n'
                    '      <action name="HideCursor" />\n'
                    "    </keybind>\n"
                    "    <!-- pi-kiosk-setup:cursor-hide-end -->\n"
                    "  </keyboard>\n"
                    "</labwc_config>\n"
                )
            }
        )

        WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        rc_xml = host.files[path]
        self.assertEqual(rc_xml.count(CURSOR_RC_BEGIN), 1)
        self.assertIn(
            '      <action name="WarpCursor" x="-1" y="-1" />',
            rc_xml,
        )

    def test_rejects_missing_chromium(self):
        host = FakeHost(chromium=None)

        with self.assertRaises(RuntimeError):
            WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

    def test_rejects_missing_wtype(self):
        host = FakeHost(wtype=None)

        WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        self.assertEqual(host.installed_packages, [("wtype", "swayidle")])
        launcher = host.files[launcher_path(host.home())]
        self.assertIn("/usr/bin/wtype", launcher)

    def test_rejects_missing_swayidle(self):
        host = FakeHost(swayidle=None)

        WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        self.assertEqual(host.installed_packages, [("wtype", "swayidle")])
        launcher = host.files[launcher_path(host.home())]
        self.assertIn("/usr/bin/swayidle", launcher)

    def test_converts_openbox_root_to_labwc_root_before_writing_keybinds(self):
        path = "/home/pi/.config/labwc/rc.xml"
        host = FakeHost(
            files={
                path: (
                    '<?xml version="1.0"?>\n'
                    '<openbox_config xmlns="http://openbox.org/3.4/rc">\n'
                    "  <keyboard>\n"
                    "    <default />\n"
                    "  </keyboard>\n"
                    "</openbox_config>\n"
                )
            }
        )

        WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        rc_xml = host.files[path]
        self.assertIn("<labwc_config", rc_xml)
        self.assertNotIn("<openbox_config", rc_xml)
        self.assertIn('<keybind key="A-W-h">', rc_xml)

    def test_passes_subdirectory_sources_to_host(self):
        host = FakeHost(
            deployed_webapp=WebAppDeployment(
                repo_ref="Visivalab/etruscos_touch",
                app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
                artifact_dir="dist",
            )
        )

        WebAppKioskStep().apply(
            host,
            WebAppSource(
                repo_ref="Visivalab/etruscos_touch",
                subdir="screen_1_de",
            ),
        )

        self.assertEqual(
            host.webapp_deploy_requests,
            [
                (
                    WebAppSource(
                        repo_ref="Visivalab/etruscos_touch",
                        subdir="screen_1_de",
                    ),
                    ("build", "dist"),
                )
            ],
        )

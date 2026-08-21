import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.host import WebAppDeployment, WebAppSource
from pi_kiosk.steps.webapp_kiosk import (
    CURSOR_RC_BEGIN,
    KIOSK_AUTOSTART_BEGIN,
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
    def test_opens_app_now_when_user_confirms(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "GitHub repo": "Visivalab/demo-app",
                "Open the app now?": "y",
            }
        )
        step = WebAppKioskStep()
        source = step.ask(ui)

        report = step.apply(host, source)

        self.assertEqual(
            host.launched_kiosk_paths,
            [launcher_path(host.home())],
        )
        self.assertEqual(
            host.desktop_session_commands,
            [
                ["labwc", "--reconfigure"],
            ],
        )
        self.assertIn("opened now", report.lower())

    def test_does_not_open_app_now_when_user_declines(self):
        host = FakeHost()
        ui = FakeUI(
            answers={
                "GitHub repo": "Visivalab/demo-app",
                "Open the app now?": "n",
            }
        )
        step = WebAppKioskStep()
        source = step.ask(ui)

        report = step.apply(host, source)

        self.assertEqual(host.launched_kiosk_paths, [])
        self.assertNotIn("opened now", report.lower())

    def test_deploys_build_and_writes_one_autostart_block(self):
        host = FakeHost(
            deployed_webapp=WebAppDeployment(
                repo_ref="Visivalab/demo-app",
                app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
                artifact_dir="build",
            )
        )
        step = WebAppKioskStep()
        step.ask(FakeUI(answers={"GitHub repo": "Visivalab/demo-app", "Open the app now?": "n"}))

        report = step.apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        self.assertEqual(
            host.webapp_deploy_requests,
            [(WebAppSource(repo_ref="Visivalab/demo-app"), ("build", "dist"))],
        )
        autostart = host.files["/home/pi/.config/labwc/autostart"]
        self.assertIn(KIOSK_AUTOSTART_BEGIN, autostart)
        self.assertIn(f"bash {launcher_path(host.home())}", autostart)
        rc_xml = host.files["/home/pi/.config/labwc/rc.xml"]
        self.assertIn(CURSOR_RC_BEGIN, rc_xml)
        self.assertIn('<keybind key="W-F12">', rc_xml)
        self.assertIn('<action name="HideCursor" />', rc_xml)
        launcher = host.files[launcher_path(host.home())]
        self.assertIn("python3 -m http.server 8080 --bind 127.0.0.1", launcher)
        self.assertIn('idle_pid=""', launcher)
        self.assertIn("if command -v wtype >/dev/null 2>&1; then", launcher)
        self.assertIn('(sleep 1; wtype -M logo -k F12 >/dev/null 2>&1 || true) &', launcher)
        self.assertIn("swayidle timeout 5 'wtype -M logo -k F12 >/dev/null 2>&1 || true'", launcher)
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

        report = WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

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
            '      <action name="WarpCursor" to="output" x="8" y="8" />',
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
                    '    <keybind key="W-F12">\n'
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
            '      <action name="WarpCursor" to="output" x="8" y="8" />',
            rc_xml,
        )

    def test_rejects_missing_chromium(self):
        host = FakeHost(chromium=None)

        with self.assertRaises(RuntimeError):
            WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

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

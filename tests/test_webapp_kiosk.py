import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.host import WebAppDeployment, WebAppSource
from pi_kiosk.steps.webapp_kiosk import (
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
    def test_deploys_build_and_writes_one_autostart_block(self):
        host = FakeHost(
            deployed_webapp=WebAppDeployment(
                repo_ref="Visivalab/demo-app",
                app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
                artifact_dir="build",
            )
        )

        report = WebAppKioskStep().apply(host, WebAppSource(repo_ref="Visivalab/demo-app"))

        self.assertEqual(
            host.webapp_deploy_requests,
            [(WebAppSource(repo_ref="Visivalab/demo-app"), ("build", "dist"))],
        )
        autostart = host.files["/home/pi/.config/labwc/autostart"]
        self.assertIn(KIOSK_AUTOSTART_BEGIN, autostart)
        self.assertIn(f"bash {launcher_path(host.home())}", autostart)
        launcher = host.files[launcher_path(host.home())]
        self.assertIn("python3 -m http.server 8080 --bind 127.0.0.1", launcher)
        self.assertIn("chromium-browser", launcher)
        self.assertIn("http://127.0.0.1:8080", launcher)
        self.assertIn("/home/pi/.local/share/pi-kiosk/webapp/current", launcher)
        self.assertIn("build", report.lower())

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

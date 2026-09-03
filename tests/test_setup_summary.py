import unittest

from tests.fake_ui import FakeUI
from tests.fakes import FakeHost

from pi_kiosk.host import VideoSource, WebAppDeployment, WebAppSource
from pi_kiosk.setup_summary import (
    AUTOLOGIN_SUMMARY_KEY,
    NOSLEEP_SUMMARY_KEY,
    ROTATION_SUMMARY_KEY,
    RUSTDESK_SUMMARY_KEY,
    TOTEM_REGISTRATION_SUMMARY_KEY,
    TOUCH_SUMMARY_KEY,
    VIDEO_SUMMARY_KEY,
    WEBAPP_SUMMARY_KEY,
    RotationSummary,
    RustDeskSummary,
    TotemRegistrationSummary,
    TouchSummary,
    VideoSummary,
    WebAppSummary,
    render_setup_summary,
)
from pi_kiosk.steps.project_kiosk import ProjectSelection, ProjectKioskStep
from pi_kiosk.steps.setup_summary import SetupSummaryStep
from pi_kiosk.steps.video_kiosk import VideoKioskRequest
from pi_kiosk.steps.webapp_kiosk import WebAppKioskRequest, WebAppKioskStep
from pi_kiosk.totem_registration import TotemRegistrationRequest
from pi_kiosk.wizard_context import WizardContext


class RenderSetupSummaryTests(unittest.TestCase):
    def test_renders_webapp_summary_with_skipped_registration(self):
        host = FakeHost()
        context = WizardContext(host=host, ui=FakeUI())
        context.record_answer(
            ProjectKioskStep.id,
            ProjectSelection(
                project_type="webapp",
                request=WebAppKioskRequest(source=WebAppSource(repo_ref="Visivalab/demo-app")),
            ),
        )
        context.record_answer("register-totem", None)
        context.state[ROTATION_SUMMARY_KEY] = RotationSummary(
            choice_id="clockwise",
            output="HDMI-A-1",
            applied_live=True,
        )
        context.state[TOUCH_SUMMARY_KEY] = TouchSummary(outcome="not-detected")
        context.state[NOSLEEP_SUMMARY_KEY] = True
        context.state[AUTOLOGIN_SUMMARY_KEY] = True
        context.state[RUSTDESK_SUMMARY_KEY] = RustDeskSummary(rustdesk_id="123 456 789")
        context.state[WEBAPP_SUMMARY_KEY] = WebAppSummary(
            repo_ref="Visivalab/demo-app",
            source_subdir="",
            artifact_dir="build",
            app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
            launcher_path="/home/pi/.config/pi-kiosk/webapp-kiosk.sh",
            server_url="http://127.0.0.1:8080",
            log_tail_command="tail -f /home/pi/.local/state/pi-kiosk/webapp-server.log",
            heartbeat_log_tail_command=(
                "tail -f /home/pi/.local/state/pi-kiosk/webapp-heartbeat.log"
            ),
        )
        context.state[TOTEM_REGISTRATION_SUMMARY_KEY] = TotemRegistrationSummary(status="skipped")

        report = render_setup_summary(context)

        self.assertTrue(report.startswith("Done: setup summary"))
        self.assertIn(
            "- [x] Screen rotation set to clockwise on HDMI-A-1 and applied live; it will persist on future graphical logins",
            report,
        )
        self.assertIn(
            "- [x] RustDesk unattended access was installed and configured with ID 123 456 789",
            report,
        )
        self.assertIn("- [x] Found build output in build/", report)
        self.assertIn(
            "- [x] Deployed the webapp to /home/pi/.local/share/pi-kiosk/webapp/current",
            report,
        )
        self.assertIn(
            "- [x] Configured labwc autostart to launch the kiosk on the next graphical login",
            report,
        )
        self.assertIn("- [x] Configured automatic mouse hide after idle", report)
        self.assertIn("- [x] Totem registration was skipped", report)

    def test_webapp_apply_writes_summary_state_with_subdirectory(self):
        host = FakeHost(
            deployed_webapp=WebAppDeployment(
                repo_ref="Visivalab/etruscos_touch",
                artifact_dir="dist",
                app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
            )
        )
        ui = FakeUI()
        context = WizardContext(host=host, ui=ui)
        selection = ProjectSelection(
            project_type="webapp",
            request=WebAppKioskRequest(
                source=WebAppSource(
                    repo_ref="Visivalab/etruscos_touch",
                    subdir="screen_1_de",
                )
            ),
        )
        context.record_answer(ProjectKioskStep.id, selection)
        context.state[ROTATION_SUMMARY_KEY] = RotationSummary(
            choice_id="clockwise",
            output="HDMI-A-1",
            applied_live=True,
        )
        context.state[TOUCH_SUMMARY_KEY] = TouchSummary(outcome="not-detected")
        context.state[NOSLEEP_SUMMARY_KEY] = True
        context.state[AUTOLOGIN_SUMMARY_KEY] = True
        context.state[RUSTDESK_SUMMARY_KEY] = RustDeskSummary(rustdesk_id="123 456 789")
        context.state[TOTEM_REGISTRATION_SUMMARY_KEY] = TotemRegistrationSummary(status="skipped")

        WebAppKioskStep(prompt_for_next_action=False).apply(
            host,
            selection.request,
            context,
        )
        report = SetupSummaryStep().apply(host, context=context)

        self.assertEqual(
            context.state[WEBAPP_SUMMARY_KEY],
            WebAppSummary(
                repo_ref="Visivalab/etruscos_touch",
                source_subdir="screen_1_de",
                artifact_dir="dist",
                app_dir="/home/pi/.local/share/pi-kiosk/webapp/current",
                launcher_path="/home/pi/.config/pi-kiosk/webapp-kiosk.sh",
                server_url="http://127.0.0.1:8080",
                log_tail_command="tail -f /home/pi/.local/state/pi-kiosk/webapp-server.log",
                heartbeat_log_tail_command=(
                    "tail -f /home/pi/.local/state/pi-kiosk/webapp-heartbeat.log"
                ),
            ),
        )
        self.assertIn(
            "- [x] Downloaded the webapp from Visivalab/etruscos_touch (subdirectory: screen_1_de/)",
            report,
        )
        self.assertIn("- [x] Found build output in dist/", report)

    def test_renders_video_summary_with_totem_registration_details(self):
        host = FakeHost(machine_name="pi-kiosk-01")
        context = WizardContext(host=host, ui=FakeUI())
        context.record_answer(
            ProjectKioskStep.id,
            ProjectSelection(
                project_type="video",
                request=VideoKioskRequest(
                    source=VideoSource(
                        shared_url="https://www.dropbox.com/s/example/demo.mp4?dl=0",
                        download_url="https://www.dropbox.com/s/example/demo.mp4?dl=1",
                    )
                ),
            ),
        )
        context.record_answer(
            "register-totem",
            TotemRegistrationRequest(
                totem_type="video",
                totem_name="Hall Screen",
                description="",
                location="",
            ),
        )
        context.state[ROTATION_SUMMARY_KEY] = RotationSummary(
            choice_id="none",
            output="HDMI-A-1",
            applied_live=False,
        )
        context.state[TOUCH_SUMMARY_KEY] = TouchSummary(outcome="not-needed")
        context.state[NOSLEEP_SUMMARY_KEY] = True
        context.state[AUTOLOGIN_SUMMARY_KEY] = True
        context.state[RUSTDESK_SUMMARY_KEY] = RustDeskSummary(rustdesk_id="987 654 321")
        context.state[VIDEO_SUMMARY_KEY] = VideoSummary(
            shared_url="https://www.dropbox.com/s/example/demo.mp4?dl=0",
            file_name="demo.mp4",
            video_path="/home/pi/.local/share/pi-kiosk/video/current/demo.mp4",
            launcher_path="/home/pi/.config/pi-kiosk/video-kiosk.sh",
        )
        context.state[TOTEM_REGISTRATION_SUMMARY_KEY] = TotemRegistrationSummary(
            status="registered",
            machine_name="pi-kiosk-01",
            totem_name="Hall Screen",
            detail="Hourly status reporter installed.",
        )

        report = render_setup_summary(context)

        self.assertIn(
            "- [x] Screen rotation set to no rotation on HDMI-A-1; it will apply on the next graphical login",
            report,
        )
        self.assertIn(
            "- [x] Touch screen detected, but no mapping changes were needed because the screen is not rotated",
            report,
        )
        self.assertIn("- [x] Project selected: video", report)
        self.assertIn(
            "- [x] Downloaded the video from https://www.dropbox.com/s/example/demo.mp4?dl=0",
            report,
        )
        self.assertIn(
            "- [x] Deployed the video file to /home/pi/.local/share/pi-kiosk/video/current/demo.mp4",
            report,
        )
        self.assertIn("- [x] Configured mpv for fullscreen looping playback", report)
        self.assertIn(
            '- [x] Registered totem "Hall Screen" for machine pi-kiosk-01. Hourly status reporter installed.',
            report,
        )

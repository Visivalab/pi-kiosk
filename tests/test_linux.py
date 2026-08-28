import json
import subprocess
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest import mock
from urllib import error

from pi_kiosk.errors import UserFacingError
from pi_kiosk.host import TotemConnectionDetails, TotemStatusReporterConfig, VideoSource
from pi_kiosk.linux import (
    LinuxHost,
    NeedSudoUser,
    _libinput_reports_touch,
    _select_rustdesk_deb_asset,
)


class FakeResponse(BytesIO):
    def __init__(
        self,
        payload: bytes,
        headers: dict[str, str] | None = None,
        status: int = 200,
    ) -> None:
        super().__init__(payload)
        self.headers = headers or {}
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self) -> int:
        return self.status


class LinuxHostTests(unittest.TestCase):
    def test_root_shell_without_sudo_user_is_rejected(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            with mock.patch("os.geteuid", return_value=0):
                with self.assertRaises(NeedSudoUser):
                    LinuxHost().user()

    def test_mkdir_owns_each_directory_under_the_desktop_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home" / "pi"
            target = home / ".config" / "labwc"
            owned: list[Path] = []
            host = LinuxHost()

            with mock.patch.object(host, "home", return_value=str(home)):
                with mock.patch.object(host, "_own", side_effect=owned.append):
                    host.mkdir(str(target))

            self.assertTrue(target.is_dir())
            self.assertEqual(
                owned,
                [
                    target,
                    target.parent,
                    home,
                ],
            )

    def test_libinput_touch_detection_reports_true_for_touch_capability(self):
        self.assertTrue(
            _libinput_reports_touch(
                "Device: Foo\nCapabilities: keyboard pointer touch\n"
            )
        )

    def test_libinput_touch_detection_reports_false_without_touch_capability(self):
        self.assertFalse(
            _libinput_reports_touch(
                "Device: Foo\nCapabilities: keyboard pointer\n"
            )
        )

    def test_selects_arm64_rustdesk_deb_asset(self):
        asset = _select_rustdesk_deb_asset(
            {
                "assets": [
                    {"name": "rustdesk-1.4.3-x86_64.deb", "browser_download_url": "x"},
                    {"name": "rustdesk-1.4.3-aarch64.deb", "browser_download_url": "a"},
                ]
            },
            "arm64",
        )
        self.assertEqual(asset["name"], "rustdesk-1.4.3-aarch64.deb")

    def test_rejects_unsupported_rustdesk_architecture(self):
        with self.assertRaises(UserFacingError):
            _select_rustdesk_deb_asset({"assets": []}, "mips")

    def test_installs_missing_cursor_packages_with_apt(self):
        host = LinuxHost()

        with mock.patch("shutil.which", side_effect=["/usr/bin/wtype", "/usr/bin/swayidle"]):
            with mock.patch("subprocess.run") as run:
                host.ensure_packages_installed(("wtype", "swayidle"))

        run.assert_called_once_with(
            ["apt-get", "install", "-y", "wtype", "swayidle"],
            check=True,
            text=True,
        )

    def test_launch_kiosk_now_reconfigures_before_background_launch(self):
        host = LinuxHost()

        with mock.patch.object(host, "run_in_desktop_session") as run:
            host.launch_kiosk_now("/home/pi/.config/pi-kiosk/webapp-kiosk.sh")

        run.assert_called_once_with(
            [
                "sh",
                "-lc",
                "labwc --reconfigure >/dev/null 2>&1 || true; sleep 1; nohup bash /home/pi/.config/pi-kiosk/webapp-kiosk.sh >/dev/null 2>&1 </dev/null &",
            ],
            check=True,
        )

    def test_launch_webapp_server_now_starts_server_only_mode(self):
        host = LinuxHost()

        with mock.patch.object(host, "run_in_desktop_session") as run:
            host.launch_webapp_server_now("/home/pi/.config/pi-kiosk/webapp-kiosk.sh")

        run.assert_called_once_with(
            [
                "sh",
                "-lc",
                "nohup bash /home/pi/.config/pi-kiosk/webapp-kiosk.sh server-only >/dev/null 2>&1 </dev/null &",
            ],
            check=True,
        )

    def test_download_file_reports_percentage_progress_when_size_is_known(self):
        host = LinuxHost()
        progress: list[str] = []

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "demo.mp4"

            with mock.patch(
                "urllib.request.urlopen",
                return_value=FakeResponse(
                    b"x" * 16,
                    headers={"Content-Length": "16"},
                ),
            ):
                host._download_file(
                    "https://example.com/demo.mp4",
                    target,
                    description="video file",
                    progress=progress.append,
                )

            self.assertEqual(target.read_bytes(), b"x" * 16)

        self.assertEqual(
            progress,
            [
                "Downloading video file (0%)",
                "Downloading video file (100%)",
            ],
        )

    def test_deploy_video_rejects_html_content(self):
        host = LinuxHost()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home" / "pi"
            home.mkdir(parents=True)

            with mock.patch.object(host, "home", return_value=str(home)):
                with mock.patch.object(host, "_own_within_home"):
                    with mock.patch.object(host, "_own_tree"):
                        with mock.patch(
                            "urllib.request.urlopen",
                            return_value=FakeResponse(
                                b"<html>login</html>",
                                headers={"Content-Type": "text/html"},
                            ),
                        ):
                            with self.assertRaisesRegex(UserFacingError, "video file"):
                                host.deploy_video(
                                    VideoSource(
                                        shared_url="https://www.dropbox.com/s/example/demo.mp4",
                                        download_url="https://www.dropbox.com/s/example/demo.mp4?dl=1",
                                    )
                                )

    def test_deploy_video_uses_content_disposition_filename(self):
        host = LinuxHost()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home" / "pi"
            home.mkdir(parents=True)

            with mock.patch.object(host, "home", return_value=str(home)):
                with mock.patch.object(host, "_own_within_home"):
                    with mock.patch.object(host, "_own_tree"):
                        with mock.patch(
                            "urllib.request.urlopen",
                            return_value=FakeResponse(
                                b"x" * 8,
                                headers={
                                    "Content-Type": "video/mp4",
                                    "Content-Length": "8",
                                    "Content-Disposition": 'attachment; filename="real-name.mp4"',
                                },
                            ),
                        ):
                            deployment = host.deploy_video(
                                VideoSource(
                                    shared_url="https://www.dropbox.com/s/example/demo.mp4",
                                    download_url="https://www.dropbox.com/s/example/demo.mp4?dl=1",
                                )
                            )

            self.assertEqual(deployment.file_name, "real-name.mp4")
            self.assertEqual(
                deployment.video_path,
                str(home / ".local" / "share" / "pi-kiosk" / "video" / "current" / "real-name.mp4"),
            )

    def test_deploy_video_rejects_truncated_downloads(self):
        host = LinuxHost()

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home" / "pi"
            home.mkdir(parents=True)

            with mock.patch.object(host, "home", return_value=str(home)):
                with mock.patch.object(host, "_own_within_home"):
                    with mock.patch.object(host, "_own_tree"):
                        with mock.patch(
                            "urllib.request.urlopen",
                            return_value=FakeResponse(
                                b"short",
                                headers={
                                    "Content-Type": "video/mp4",
                                    "Content-Length": "10",
                                },
                            ),
                        ):
                            with self.assertRaisesRegex(UserFacingError, "incomplete"):
                                host.deploy_video(
                                    VideoSource(
                                        shared_url="https://www.dropbox.com/s/example/demo.mp4",
                                        download_url="https://www.dropbox.com/s/example/demo.mp4?dl=1",
                                    )
                                )

    def test_register_totem_posts_json_payload_with_machine_name(self):
        host = LinuxHost()

        with mock.patch("socket.gethostname", return_value="minipc-07"):
            with mock.patch("pi_kiosk.linux._machine_id", return_value="machine-123"):
                with mock.patch(
                    "urllib.request.urlopen",
                    return_value=FakeResponse(b"{}", status=201),
                ) as urlopen:
                    host.register_totem(
                        "https://dashboard.example.com/register-new-totem",
                        "totem-secret",
                        "minipc-07",
                        "webapp",
                        "Hall Screen",
                        "Main entrance display",
                        "Reception",
                        TotemConnectionDetails(
                            rustdesk_id="987 654 321",
                            rustdesk_password="secret-pass",
                            ssh_user="pi",
                            ssh_port=2222,
                            ip_address="192.168.1.50",
                            ip_addresses=("192.168.1.50", "10.0.0.12"),
                        ),
                    )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://dashboard.example.com/register-new-totem")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Authorization"), "Bearer totem-secret")
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "totem_id": "minipc-07",
                "totemType": "webapp",
                "machineName": "minipc-07",
                "machineId": "machine-123",
                "name": "Hall Screen",
                "description": "Main entrance display",
                "location": "Reception",
                "rustdeskId": "987 654 321",
                "rustdeskPassword": "secret-pass",
                "sshUser": "pi",
                "sshPort": 2222,
                "ipAddress": "192.168.1.50",
                "ipAddresses": ["192.168.1.50", "10.0.0.12"],
                "registeredAt": mock.ANY,
            },
        )

    def test_register_totem_surfaces_backend_error_message(self):
        host = LinuxHost()
        http_error = error.HTTPError(
            "https://dashboard.example.com/register-new-totem",
            400,
            "Bad Request",
            hdrs=None,
            fp=BytesIO(b'{"message":"Totem already exists"}'),
        )

        with mock.patch("pi_kiosk.linux._machine_id", return_value="machine-123"):
            with mock.patch("urllib.request.urlopen", side_effect=http_error):
                with self.assertRaisesRegex(
                    UserFacingError,
                    "HTTP 400: Totem already exists",
                ):
                    host.register_totem(
                        "https://dashboard.example.com/register-new-totem",
                        "totem-secret",
                        "minipc-07",
                        "video",
                        "Hall Screen",
                        "Main entrance display",
                        "Reception",
                        TotemConnectionDetails(
                            rustdesk_id=None,
                            rustdesk_password=None,
                            ssh_user="pi",
                            ssh_port=22,
                            ip_address=None,
                            ip_addresses=(),
                        ),
                    )

    def test_install_totem_status_reporter_writes_files_and_enables_timer(self):
        host = LinuxHost()
        config = TotemStatusReporterConfig(
            endpoint_url="https://dashboard.example.com/totem-status",
            token="status-secret",
            totem_id="minipc-07",
            totem_type="video",
            desktop_user="kiosk",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "usr" / "local" / "lib" / "pi-kiosk" / "totem-status.py"
            status_config = root / "etc" / "pi-kiosk" / "totem-status.json"
            service = root / "etc" / "systemd" / "system" / "pi-kiosk-totem-status.service"
            timer = root / "etc" / "systemd" / "system" / "pi-kiosk-totem-status.timer"

            with mock.patch("pi_kiosk.linux.status_script_path", return_value=script):
                with mock.patch("pi_kiosk.linux.status_config_path", return_value=status_config):
                    with mock.patch("pi_kiosk.linux.status_service_path", return_value=service):
                        with mock.patch("pi_kiosk.linux.status_timer_path", return_value=timer):
                            with mock.patch.object(host, "run") as run:
                                host.install_totem_status_reporter(config)
                                self.assertTrue(script.is_file())
                                self.assertEqual(script.stat().st_mode & 0o777, 0o755)
                                self.assertIn(
                                    '"totem_type": config["totemType"]',
                                    script.read_text(encoding="utf-8"),
                                )
                                self.assertIn(
                                    '"kiosk_running": kiosk_running',
                                    script.read_text(encoding="utf-8"),
                                )
                                self.assertIn(
                                    '"totemType": "video"',
                                    status_config.read_text(encoding="utf-8"),
                                )
                                self.assertIn(
                                    '"webapp_running": webapp_running',
                                    script.read_text(encoding="utf-8"),
                                )
                                self.assertIn(
                                    "socket.gethostname().strip()",
                                    script.read_text(encoding="utf-8"),
                                )
                                self.assertEqual(
                                    json.loads(status_config.read_text(encoding="utf-8")),
                                    {
                                        "endpointUrl": "https://dashboard.example.com/totem-status",
                                        "token": "status-secret",
                                        "totemId": "minipc-07",
                                        "totemType": "video",
                                        "desktopUser": "kiosk",
                                        "port": 8080,
                                    },
                                )
                                self.assertIn(
                                    "ExecStart=/usr/bin/python3",
                                    service.read_text(encoding="utf-8"),
                                )
                                self.assertIn(
                                    "OnUnitActiveSec=1h",
                                    timer.read_text(encoding="utf-8"),
                                )
                                run.assert_has_calls(
                                    [
                                        mock.call(["systemctl", "daemon-reload"]),
                                        mock.call(
                                            ["systemctl", "enable", "--now", "pi-kiosk-totem-status.timer"]
                                        ),
                                        mock.call(
                                            ["systemctl", "start", "pi-kiosk-totem-status.service"],
                                            check=False,
                                        ),
                                    ]
                                )

    def test_install_totem_status_reporter_returns_warning_when_first_run_fails(self):
        host = LinuxHost()
        config = TotemStatusReporterConfig(
            endpoint_url="https://dashboard.example.com/totem-status",
            token="status-secret",
            totem_id="minipc-07",
            totem_type="video",
            desktop_user="kiosk",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "usr" / "local" / "lib" / "pi-kiosk" / "totem-status.py"
            status_config = root / "etc" / "pi-kiosk" / "totem-status.json"
            service = root / "etc" / "systemd" / "system" / "pi-kiosk-totem-status.service"
            timer = root / "etc" / "systemd" / "system" / "pi-kiosk-totem-status.timer"

            with mock.patch("pi_kiosk.linux.status_script_path", return_value=script):
                with mock.patch("pi_kiosk.linux.status_config_path", return_value=status_config):
                    with mock.patch("pi_kiosk.linux.status_service_path", return_value=service):
                        with mock.patch("pi_kiosk.linux.status_timer_path", return_value=timer):
                            with mock.patch.object(
                                host,
                                "run",
                                side_effect=[
                                    subprocess.CompletedProcess(
                                        ["systemctl", "daemon-reload"], 0
                                    ),
                                    subprocess.CompletedProcess(
                                        ["systemctl", "enable", "--now", "pi-kiosk-totem-status.timer"],
                                        0,
                                    ),
                                    subprocess.CompletedProcess(
                                        ["systemctl", "start", "pi-kiosk-totem-status.service"],
                                        1,
                                    ),
                                ],
                            ) as run:
                                warning = host.install_totem_status_reporter(config)

        self.assertIsNotNone(warning)
        self.assertIn("first status run failed", warning)
        self.assertIn("journalctl -u pi-kiosk-totem-status.service", warning)
        run.assert_has_calls(
            [
                mock.call(["systemctl", "daemon-reload"]),
                mock.call(["systemctl", "enable", "--now", "pi-kiosk-totem-status.timer"]),
                mock.call(["systemctl", "start", "pi-kiosk-totem-status.service"], check=False),
            ]
        )

if __name__ == "__main__":
    unittest.main()

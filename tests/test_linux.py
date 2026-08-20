import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pi_kiosk.errors import UserFacingError
from pi_kiosk.linux import (
    LinuxHost,
    NeedSudoUser,
    _libinput_reports_touch,
    _select_rustdesk_deb_asset,
)


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


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pi_kiosk.linux import LinuxHost, NeedSudoUser


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


if __name__ == "__main__":
    unittest.main()

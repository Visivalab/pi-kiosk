from __future__ import annotations

import getpass
import os
import pwd
import subprocess
from pathlib import Path

from pi_kiosk.detect import looks_like_raspberry_pi


class LinuxHost:
    """Talks to the real machine. Keep this thin; logic lives in the steps."""

    def home(self) -> str:
        return str(Path(pwd.getpwnam(self.user()).pw_dir))

    def user(self) -> str:
        return os.environ.get("SUDO_USER") or getpass.getuser()

    def is_raspberry_pi(self) -> bool:
        return looks_like_raspberry_pi(
            model=_read_device_tree_model(),
            has_rpi_issue=Path("/etc/rpi-issue").is_file(),
        )

    def is_root(self) -> bool:
        return os.geteuid() == 0

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def mkdir(self, path: str) -> None:
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        self._own(directory)

    def read_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._own(target.parent)
        target.write_text(content, encoding="utf-8")
        if target.name == "autostart":
            target.chmod(0o755)
        self._own(target)

    def detect_wayland_output(self) -> str | None:
        try:
            result = subprocess.run(
                ["wlr-randr"],
                check=False,
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            return None
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line and not line[0].isspace():
                return line.split()[0]
        return None

    def run(self, argv: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, check=check, text=True)

    def _own(self, path: Path) -> None:
        if not self.is_root():
            return
        try:
            info = pwd.getpwnam(self.user())
        except KeyError:
            return
        os.chown(path, info.pw_uid, info.pw_gid)


def _read_device_tree_model() -> str | None:
    for candidate in (
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    ):
        try:
            raw = candidate.read_bytes()
        except OSError:
            continue
        return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
    return None

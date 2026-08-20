from __future__ import annotations

import getpass
import os
import pwd
import subprocess
from pathlib import Path

from pi_kiosk.detect import looks_like_raspberry_pi


class NeedSudoUser(RuntimeError):
    """The tool must know which desktop user's home to modify."""


class LinuxHost:
    """Talks to the real machine. Keep this thin; logic lives in the steps."""

    def home(self) -> str:
        return str(Path(pwd.getpwnam(self.user()).pw_dir))

    def user(self) -> str:
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            return sudo_user
        if self.is_root():
            raise NeedSudoUser(
                "Run this tool with sudo from the desktop user account. "
                "Nothing was changed."
            )
        return getpass.getuser()

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
        self._own_within_home(directory)

    def read_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._own_within_home(target.parent)
        target.write_text(content, encoding="utf-8")
        if target.name == "autostart":
            target.chmod(0o755)
        self._own(target)

    def detect_wayland_output(self) -> str | None:
        result = self.run_in_desktop_session(["wlr-randr"], check=False)
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line and not line[0].isspace():
                return line.split()[0]
        return None

    def run(self, argv: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, check=check, text=True)

    def run_in_desktop_session(
        self,
        argv: list[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = self._desktop_session_env()
        if env is None:
            result = subprocess.CompletedProcess(
                args=list(argv),
                returncode=1,
                stdout="",
                stderr="No desktop Wayland session detected.",
            )
            if check:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    argv,
                    output=result.stdout,
                    stderr=result.stderr,
                )
            return result

        if self.is_root():
            command = ["sudo", "-u", self.user(), "env"]
            command.extend(f"{name}={value}" for name, value in env.items())
            command.extend(argv)
            return subprocess.run(
                command,
                check=check,
                text=True,
                capture_output=True,
            )

        merged_env = os.environ.copy()
        merged_env.update(env)
        return subprocess.run(
            argv,
            check=check,
            text=True,
            capture_output=True,
            env=merged_env,
        )

    def _own(self, path: Path) -> None:
        if not self.is_root():
            return
        try:
            info = pwd.getpwnam(self.user())
        except KeyError:
            return
        os.chown(path, info.pw_uid, info.pw_gid)

    def _own_within_home(self, path: Path) -> None:
        home = Path(self.home())
        current = path
        while current == home or home in current.parents:
            self._own(current)
            if current == home:
                break
            current = current.parent

    def _desktop_session_env(self) -> dict[str, str] | None:
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        wayland_display = os.environ.get("WAYLAND_DISPLAY")

        if self.is_root():
            user_info = pwd.getpwnam(self.user())
            runtime_dir = runtime_dir or f"/run/user/{user_info.pw_uid}"

        if not runtime_dir:
            return None

        runtime_path = Path(runtime_dir)
        if not runtime_path.is_dir():
            return None

        if not wayland_display:
            sockets = sorted(runtime_path.glob("wayland-*"))
            if not sockets:
                return None
            wayland_display = sockets[0].name

        return {
            "XDG_RUNTIME_DIR": str(runtime_path),
            "WAYLAND_DISPLAY": wayland_display,
        }


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

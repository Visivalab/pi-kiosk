from __future__ import annotations

import re
import shlex
from typing import Callable
from urllib.parse import urlparse

from pi_kiosk.errors import UserFacingError
from pi_kiosk.files import read_or_empty, upsert_marked_block
from pi_kiosk.host import Host, WebAppSource
from pi_kiosk.ui import UI

KIOSK_AUTOSTART_BEGIN = "# pi-kiosk-setup:webapp-kiosk-begin"
KIOSK_AUTOSTART_END = "# pi-kiosk-setup:webapp-kiosk-end"
LEGACY_CURSOR_AUTOSTART_BEGIN = "# pi-kiosk-setup:cursor-hide-begin"
LEGACY_CURSOR_AUTOSTART_END = "# pi-kiosk-setup:cursor-hide-end"
CURSOR_RC_BEGIN = "<!-- pi-kiosk-setup:cursor-hide-begin -->"
CURSOR_RC_END = "<!-- pi-kiosk-setup:cursor-hide-end -->"
KIOSK_PORT = 8080
CURSOR_IDLE_SECONDS = 5
_RC_XML_HEADER = '<?xml version="1.0"?>\n<labwc_config>\n'
_RC_XML_FOOTER = "</labwc_config>\n"
_REPO_PROMPT = "GitHub repo"
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HIDE_CURSOR_COMMAND = "wtype -M logo -k F12 >/dev/null 2>&1 || true"


def normalize_source(value: str) -> WebAppSource:
    text = value.strip()
    if not text:
        raise ValueError("Enter a GitHub repo in owner/repo format.")

    if text.startswith("https://github.com/"):
        return _normalize_github_url(text)

    if not _REPO_PATTERN.fullmatch(text):
        raise ValueError("Enter the repo as owner/repo or a full GitHub URL.")
    return WebAppSource(repo_ref=text)


def _normalize_github_url(value: str) -> WebAppSource:
    parsed = urlparse(value)
    path = parsed.path.removesuffix(".git").strip("/")
    parts = [part for part in path.split("/") if part]
    if len(parts) < 2:
        raise ValueError("Enter the repo as owner/repo or a full GitHub URL.")

    repo_ref = "/".join(parts[:2])
    if not _REPO_PATTERN.fullmatch(repo_ref):
        raise ValueError("Enter the repo as owner/repo or a full GitHub URL.")

    if len(parts) == 2:
        return WebAppSource(repo_ref=repo_ref)

    if len(parts) >= 4 and parts[2] == "tree":
        subdir = "/".join(parts[4:]).strip("/")
        if not subdir:
            raise ValueError("GitHub tree URLs must include a subdirectory path.")
        return WebAppSource(repo_ref=repo_ref, subdir=subdir)

    raise ValueError("Enter the repo as owner/repo or a full GitHub URL.")


def launcher_path(home: str) -> str:
    return f"{home}/.config/pi-kiosk/webapp-kiosk.sh"


def launcher_script(browser: str, app_dir: str) -> str:
    quoted_dir = shlex.quote(app_dir)
    quoted_browser = shlex.quote(browser)
    url = f"http://127.0.0.1:{KIOSK_PORT}"
    idle_command = (
        f"swayidle timeout {CURSOR_IDLE_SECONDS} "
        f"'{_HIDE_CURSOR_COMMAND}' >/dev/null 2>&1 &"
    )
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"APP_DIR={quoted_dir}",
            f"URL={shlex.quote(url)}",
            'LOG_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/pi-kiosk"',
            'LOG_FILE="$LOG_ROOT/webapp-server.log"',
            'idle_pid=""',
            'mkdir -p "$LOG_ROOT"',
            'cd "$APP_DIR"',
            f'python3 -m http.server {KIOSK_PORT} --bind 127.0.0.1 >"$LOG_FILE" 2>&1 &',
            'server_pid="$!"',
            'cleanup() {',
            '  kill "$server_pid" >/dev/null 2>&1 || true',
            '  if [ -n "$idle_pid" ]; then',
            '    kill "$idle_pid" >/dev/null 2>&1 || true',
            '  fi',
            '}',
            'trap cleanup EXIT',
            "for _ in 1 2 3 4 5; do",
            "  if python3 -c \"import socket, sys; sock = socket.socket(); sock.settimeout(0.2); code = sock.connect_ex(('127.0.0.1', 8080)); sock.close(); sys.exit(0 if code == 0 else 1)\" >/dev/null 2>&1; then",
            "    break",
            "  fi",
            "  sleep 0.2",
            "done",
            "if command -v wtype >/dev/null 2>&1; then",
            f"  (sleep 1; {_HIDE_CURSOR_COMMAND}) &",
            "fi",
            "if command -v wtype >/dev/null 2>&1 && command -v swayidle >/dev/null 2>&1; then",
            f"  {idle_command}",
            '  idle_pid="$!"',
            "fi",
            f'{quoted_browser} --kiosk --incognito --noerrdialogs --disable-infobars "$URL"',
            "",
        ]
    )


def remove_marked_block(original: str, begin: str, end: str) -> str:
    if begin not in original or end not in original:
        return original
    pre, rest = original.split(begin, 1)
    _, post = rest.split(end, 1)
    if post.startswith("\n"):
        post = post[1:]
    return pre + post


def cursor_keybind_block(indent: str = "    ") -> str:
    action_indent = f"{indent}  "
    return "\n".join(
        [
            f"{indent}{CURSOR_RC_BEGIN}",
            f'{indent}<keybind key="W-F12">',
            f'{action_indent}<action name="WarpCursor" to="output" x="8" y="8" />',
            f'{action_indent}<action name="HideCursor" />',
            f"{indent}</keybind>",
            f"{indent}{CURSOR_RC_END}",
        ]
    )


def upsert_cursor_keybind(original: str) -> str:
    block = cursor_keybind_block()
    keyboard_section = "\n".join(
        [
            "  <keyboard>",
            "    <default />",
            block,
            "  </keyboard>",
        ]
    )
    if not original.strip():
        return f"{_RC_XML_HEADER}{keyboard_section}\n{_RC_XML_FOOTER}"
    if CURSOR_RC_BEGIN in original and CURSOR_RC_END in original:
        pre, rest = original.split(CURSOR_RC_BEGIN, 1)
        _, post = rest.split(CURSOR_RC_END, 1)
        if post.startswith("\n"):
            post = post[1:]
        return f"{pre}{block}\n{post}"

    keyboard_self_closing = "  <keyboard />"
    if keyboard_self_closing in original:
        return original.replace(keyboard_self_closing, keyboard_section, 1)

    keyboard_close = "  </keyboard>"
    if keyboard_close in original:
        before, after = original.rsplit(keyboard_close, 1)
        if before and not before.endswith("\n"):
            before += "\n"
        return f"{before}{block}\n{keyboard_close}{after}"

    closing = "</labwc_config>"
    if closing in original:
        before, after = original.rsplit(closing, 1)
        if before and not before.endswith("\n"):
            before += "\n"
        return f"{before}{keyboard_section}\n{closing}{after}"

    if original and not original.endswith("\n"):
        original += "\n"
    return f"{original}{keyboard_section}\n"


class WebAppKioskStep:
    id = "webapp-kiosk"
    title = _REPO_PROMPT
    choices = ()
    interactive = True

    def __init__(self) -> None:
        self._progress = None
        self._confirm: Callable[[str, bool], bool] | None = None

    def ask(self, ui: UI) -> WebAppSource:
        self._progress = ui.progress
        self._confirm = ui.confirm
        while True:
            raw = ui.prompt(self.title)
            try:
                return normalize_source(raw)
            except ValueError as exc:
                ui.warn(str(exc))

    def apply(self, host: Host, source: WebAppSource) -> str:
        progress = self._progress or (lambda _message: None)
        deployment = host.deploy_webapp(source, ("build", "dist"), progress=progress)
        browser = host.chromium_command()
        if browser is None:
            raise UserFacingError(
                "Chromium was not found on this Pi. Install Chromium and run the wizard again."
            )

        home = host.home()
        host.mkdir(f"{home}/.config/pi-kiosk")
        host.write_file(
            launcher_path(home),
            launcher_script(browser, deployment.app_dir),
        )

        autostart_path = f"{home}/.config/labwc/autostart"
        host.mkdir(f"{home}/.config/labwc")
        autostart = remove_marked_block(
            read_or_empty(host, autostart_path),
            LEGACY_CURSOR_AUTOSTART_BEGIN,
            LEGACY_CURSOR_AUTOSTART_END,
        )
        autostart = upsert_marked_block(
            autostart,
            KIOSK_AUTOSTART_BEGIN,
            KIOSK_AUTOSTART_END,
            f"bash {launcher_path(home)}",
        )
        host.write_file(autostart_path, autostart)

        rc_xml_path = f"{home}/.config/labwc/rc.xml"
        host.write_file(
            rc_xml_path,
            upsert_cursor_keybind(read_or_empty(host, rc_xml_path)),
        )

        opened_now = False
        if self._confirm is not None and self._confirm("Open the app now?", True):
            host.run_in_desktop_session(["labwc", "--reconfigure"], check=False)
            host.launch_kiosk_now(launcher_path(home))
            opened_now = True

        report = (
            f"Done: webapp kiosk deployed from {deployment.repo_ref} using "
            f"{deployment.artifact_dir}/. Chromium will start on the next graphical login."
            " If wtype and swayidle are installed, the mouse cursor will hide after idle."
        )
        if opened_now:
            report += " It was also opened now."
        return report

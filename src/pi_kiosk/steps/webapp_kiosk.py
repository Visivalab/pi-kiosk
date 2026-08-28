from __future__ import annotations

import re
import shlex
from typing import Callable
from urllib.parse import urlparse

from pi_kiosk.choice import Choice
from pi_kiosk.errors import UserFacingError
from pi_kiosk.host import Host, WebAppSource
from pi_kiosk.steps.kiosk_common import (
    CLOSE,
    CURSOR_RC_BEGIN,
    KIOSK_AUTOSTART_BEGIN,
    NEXT_ACTION_CHOICES,
    NEXT_ACTION_PROMPT,
    REBOOT,
    SIMULATE_AUTORUN,
    install_cursor_keybind,
    install_kiosk_autostart,
)
from pi_kiosk.totem_status import status_config_path, status_script_path
from pi_kiosk.ui import UI

KIOSK_PORT = 8080
CURSOR_IDLE_SECONDS = 5
_REPO_PROMPT = "GitHub repo"
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_HIDE_CURSOR_COMMAND = "-M alt -M logo -P h >/dev/null 2>&1 || true"


def action_url() -> str:
    return f"http://127.0.0.1:{KIOSK_PORT}"


def log_path(home: str) -> str:
    return f"{home}/.local/state/pi-kiosk/webapp-server.log"


def log_tail_command(home: str) -> str:
    return f"tail -f {shlex.quote(log_path(home))}"


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


def launcher_script(browser: str, app_dir: str, wtype: str, swayidle: str) -> str:
    quoted_dir = shlex.quote(app_dir)
    quoted_browser = shlex.quote(browser)
    quoted_wtype = shlex.quote(wtype)
    quoted_swayidle = shlex.quote(swayidle)
    quoted_status_reporter = shlex.quote(str(status_script_path()))
    quoted_status_config = shlex.quote(str(status_config_path()))
    url = f"http://127.0.0.1:{KIOSK_PORT}"
    idle_command = (
        f"{quoted_swayidle} timeout {CURSOR_IDLE_SECONDS} "
        f"'{quoted_wtype} {_HIDE_CURSOR_COMMAND}' >/dev/null 2>&1 &"
    )
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"APP_DIR={quoted_dir}",
            f"URL={shlex.quote(url)}",
            'MODE="${1:-kiosk}"',
            'LOG_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/pi-kiosk"',
            'LOG_FILE="$LOG_ROOT/webapp-server.log"',
            'idle_pid=""',
            'status_reporter_pid=""',
            'mkdir -p "$LOG_ROOT"',
            'cd "$APP_DIR"',
            f'python3 -m http.server {KIOSK_PORT} --bind 127.0.0.1 >"$LOG_FILE" 2>&1 &',
            'server_pid="$!"',
            'cleanup() {',
            '  kill "$server_pid" >/dev/null 2>&1 || true',
            '  if [ -n "$idle_pid" ]; then',
            '    kill "$idle_pid" >/dev/null 2>&1 || true',
            '  fi',
            '  if [ -n "$status_reporter_pid" ]; then',
            '    wait "$status_reporter_pid" >/dev/null 2>&1 || true',
            '  fi',
            '}',
            'trap cleanup EXIT',
            'server_ready=0',
            "for _ in 1 2 3 4 5; do",
            "  if python3 -c \"import socket, sys; sock = socket.socket(); sock.settimeout(0.2); code = sock.connect_ex(('127.0.0.1', 8080)); sock.close(); sys.exit(0 if code == 0 else 1)\" >/dev/null 2>&1; then",
            '    server_ready=1',
            "    break",
            "  fi",
            "  sleep 0.2",
            "done",
            'if [ "$server_ready" -eq 1 ]; then',
            f'  if [ -x {quoted_status_reporter} ] && [ -r {quoted_status_config} ]; then',
            f'    {quoted_status_reporter} {quoted_status_config} >/dev/null 2>&1 &',
            '    status_reporter_pid="$!"',
            "  fi",
            "fi",
            'if [ "$MODE" = "server-only" ]; then',
            '  wait "$server_pid"',
            "  exit 0",
            "fi",
            f"if [ -x {quoted_wtype} ]; then",
            f"  (sleep 1; {quoted_wtype} {_HIDE_CURSOR_COMMAND}) &",
            "fi",
            f"if [ -x {quoted_wtype} ] && [ -x {quoted_swayidle} ]; then",
            f"  {idle_command}",
            '  idle_pid="$!"',
            "fi",
            f'{quoted_browser} --kiosk --incognito --noerrdialogs --disable-infobars "$URL"',
            "",
        ]
    )

class WebAppKioskStep:
    id = "webapp-kiosk"
    title = _REPO_PROMPT
    choices = ()
    interactive = True

    def __init__(self, *, prompt_for_next_action: bool = True) -> None:
        self._progress = None
        self._choose: Callable[[str, list[Choice]], str] | None = None
        self._prompt_for_next_action = prompt_for_next_action

    def ask(self, ui: UI) -> WebAppSource:
        self._progress = ui.progress
        self._choose = ui.choose
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
        wtype = host.wtype_command()
        swayidle = host.swayidle_command()
        if wtype is None or swayidle is None:
            host.ensure_packages_installed(("wtype", "swayidle"))
            wtype = host.wtype_command()
            swayidle = host.swayidle_command()
        if wtype is None or swayidle is None:
            raise UserFacingError(
                "wtype and swayidle could not be prepared on this Pi. "
                "Install those packages and run the wizard again."
            )

        home = host.home()
        host.mkdir(f"{home}/.config/pi-kiosk")
        host.write_file(
            launcher_path(home),
            launcher_script(browser, deployment.app_dir, wtype, swayidle),
        )

        install_kiosk_autostart(host, launcher_path(home))
        install_cursor_keybind(host)

        log_report = f"Attach a terminal to the server logs with: {log_tail_command(home)}."
        report = (
            f"Done: webapp kiosk deployed from {deployment.repo_ref} using "
            f"{deployment.artifact_dir}/. Chromium will start on the next graphical login."
            f" The mouse cursor will hide after idle. {log_report}"
        )
        if self._prompt_for_next_action:
            next_action = CLOSE
            if self._choose is not None:
                next_action = self._choose(NEXT_ACTION_PROMPT, NEXT_ACTION_CHOICES)
            report = f"{report} {self.perform_next_action(host, next_action)}"
        return report

    def next_action_prompt(self) -> str:
        return NEXT_ACTION_PROMPT

    def next_action_choices(self) -> list[Choice]:
        return list(NEXT_ACTION_CHOICES)

    def perform_next_action(self, host: Host, action: str) -> str:
        home = host.home()
        log_report = f"Attach a terminal to the server logs with: {log_tail_command(home)}."
        if action == SIMULATE_AUTORUN:
            host.launch_kiosk_now(launcher_path(home))
            return (
                "Done: simulated autorun for testing. Cursor may not automatically hide "
                f"until the next graphical login. The app is on {action_url()}. {log_report}"
            )
        if action == REBOOT:
            host.reboot()
            return f"Done: rebooting now for the final production startup. {log_report}"

        host.launch_webapp_server_now(launcher_path(home))
        return (
            f"Done: the app is live on {action_url()} without opening Chromium. {log_report}"
        )

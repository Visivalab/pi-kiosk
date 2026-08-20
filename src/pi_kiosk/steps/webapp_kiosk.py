from __future__ import annotations

import re
import shlex

from pi_kiosk.errors import UserFacingError
from pi_kiosk.files import read_or_empty, upsert_marked_block
from pi_kiosk.host import Host
from pi_kiosk.ui import UI

KIOSK_AUTOSTART_BEGIN = "# pi-kiosk-setup:webapp-kiosk-begin"
KIOSK_AUTOSTART_END = "# pi-kiosk-setup:webapp-kiosk-end"
KIOSK_PORT = 8080
_REPO_PROMPT = "GitHub repo"
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def normalize_repo_ref(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("Enter a GitHub repo in owner/repo format.")

    prefix = "https://github.com/"
    if text.startswith(prefix):
        text = text[len(prefix) :]
    text = text.removesuffix(".git").strip("/")

    if not _REPO_PATTERN.fullmatch(text):
        raise ValueError("Enter the repo as owner/repo or a full GitHub URL.")
    return text


def launcher_path(home: str) -> str:
    return f"{home}/.config/pi-kiosk/webapp-kiosk.sh"


def launcher_script(browser: str, app_dir: str) -> str:
    quoted_dir = shlex.quote(app_dir)
    quoted_browser = shlex.quote(browser)
    url = f"http://127.0.0.1:{KIOSK_PORT}"
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"APP_DIR={quoted_dir}",
            f"URL={shlex.quote(url)}",
            'LOG_ROOT="${XDG_STATE_HOME:-$HOME/.local/state}/pi-kiosk"',
            'LOG_FILE="$LOG_ROOT/webapp-server.log"',
            'mkdir -p "$LOG_ROOT"',
            'cd "$APP_DIR"',
            f'python3 -m http.server {KIOSK_PORT} --bind 127.0.0.1 >"$LOG_FILE" 2>&1 &',
            'server_pid="$!"',
            'cleanup() {',
            '  kill "$server_pid" >/dev/null 2>&1 || true',
            '}',
            'trap cleanup EXIT',
            "for _ in 1 2 3 4 5; do",
            "  if python3 -c \"import socket, sys; sock = socket.socket(); sock.settimeout(0.2); code = sock.connect_ex(('127.0.0.1', 8080)); sock.close(); sys.exit(0 if code == 0 else 1)\" >/dev/null 2>&1; then",
            "    break",
            "  fi",
            "  sleep 0.2",
            "done",
            f'{quoted_browser} --kiosk --incognito --noerrdialogs --disable-infobars "$URL"',
            "",
        ]
    )


class WebAppKioskStep:
    id = "webapp-kiosk"
    title = _REPO_PROMPT
    choices = ()
    interactive = True

    def ask(self, ui: UI) -> str:
        while True:
            raw = ui.prompt(self.title)
            try:
                return normalize_repo_ref(raw)
            except ValueError as exc:
                ui.warn(str(exc))

    def apply(self, host: Host, repo_ref: str) -> str:
        deployment = host.deploy_webapp(repo_ref, ("build", "dist"))
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
        updated = upsert_marked_block(
            read_or_empty(host, autostart_path),
            KIOSK_AUTOSTART_BEGIN,
            KIOSK_AUTOSTART_END,
            f"bash {launcher_path(home)}",
        )
        host.write_file(autostart_path, updated)

        return (
            f"Done: webapp kiosk deployed from {deployment.repo_ref} using "
            f"{deployment.artifact_dir}/. Chromium will start on the next graphical login."
        )

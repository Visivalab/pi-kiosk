from __future__ import annotations

import shlex
from typing import Callable
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pi_kiosk.choice import Choice
from pi_kiosk.errors import UserFacingError
from pi_kiosk.host import Host, VideoSource
from pi_kiosk.steps.kiosk_common import (
    CLOSE,
    REBOOT,
    SIMULATE_AUTORUN,
    install_kiosk_autostart,
)
from pi_kiosk.ui import UI

DROPBOX_PROMPT = "Dropbox link"
VIDEO_NEXT_ACTION_PROMPT = "Choose what to do with the video now."
VIDEO_NEXT_ACTION_CHOICES = [
    Choice(
        id=SIMULATE_AUTORUN,
        label="Launch video now",
    ),
    Choice(
        id=REBOOT,
        label="Reboot",
    ),
    Choice(
        id=CLOSE,
        label="Do nothing",
    ),
]


def normalize_source(value: str) -> VideoSource:
    text = value.strip()
    if not text:
        raise ValueError("Enter a Dropbox shared file link.")

    parsed = urlparse(text)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("Enter a valid Dropbox shared file link over HTTPS.")
    if hostname != "dropbox.com" and not hostname.endswith(".dropbox.com"):
        raise ValueError("Enter a valid Dropbox shared file link.")
    path_parts = [part for part in parsed.path.split("/") if part]
    is_shared_file = len(path_parts) >= 2 and path_parts[0] == "s"
    is_scl_file = len(path_parts) >= 3 and path_parts[0] == "scl" and path_parts[1] == "fi"
    if not (is_shared_file or is_scl_file):
        raise ValueError("Enter a valid Dropbox shared file link.")

    query = [(key, item) for key, item in parse_qsl(parsed.query, keep_blank_values=True) if key != "dl"]
    query.append(("dl", "1"))
    download_url = urlunparse(parsed._replace(query=urlencode(query)))
    return VideoSource(shared_url=text, download_url=download_url)


def launcher_path(home: str) -> str:
    return f"{home}/.config/pi-kiosk/video-kiosk.sh"


def launcher_script(mpv: str, video_path: str) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            f"VIDEO_PATH={shlex.quote(video_path)}",
            f"MPV={shlex.quote(mpv)}",
            (
                '"$MPV" --fs --loop-file=inf --no-osc --no-osd-bar '
                '--cursor-autohide=always --input-touch-emulate-mouse=no "$VIDEO_PATH"'
            ),
            "",
        ]
    )


class VideoKioskStep:
    id = "video-kiosk"
    title = DROPBOX_PROMPT
    choices = ()
    interactive = True

    def __init__(self) -> None:
        self._progress = None
        self._choose: Callable[[str, list[object]], str] | None = None

    def ask(self, ui: UI) -> VideoSource:
        self._progress = ui.progress
        self._choose = ui.choose
        while True:
            raw = ui.prompt(self.title)
            try:
                return normalize_source(raw)
            except ValueError as exc:
                ui.warn(str(exc))

    def apply(self, host: Host, source: VideoSource) -> str:
        progress = self._progress or (lambda _message: None)
        deployment = host.deploy_video(source, progress=progress)
        mpv = host.mpv_command()
        if mpv is None:
            host.ensure_packages_installed(("mpv",))
            mpv = host.mpv_command()
        if mpv is None:
            raise UserFacingError(
                "mpv could not be prepared on this Pi. Install it and run the wizard again."
            )

        home = host.home()
        host.mkdir(f"{home}/.config/pi-kiosk")
        host.write_file(
            launcher_path(home),
            launcher_script(mpv, deployment.video_path),
        )
        install_kiosk_autostart(host, launcher_path(home))

        next_action = CLOSE
        if self._choose is not None:
            next_action = self._choose(VIDEO_NEXT_ACTION_PROMPT, VIDEO_NEXT_ACTION_CHOICES)

        action_report = "Doing nothing now."
        if next_action == SIMULATE_AUTORUN:
            host.launch_video_now(launcher_path(home))
            action_report = "Launching video now for testing."
        elif next_action == REBOOT:
            host.reboot()
            action_report = "Rebooting now for the final production startup."

        return (
            f"Done: video kiosk deployed with {deployment.file_name}. "
            f"mpv will start on the next graphical login. {action_report}"
        )

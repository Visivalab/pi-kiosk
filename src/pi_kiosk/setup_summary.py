from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pi_kiosk.wizard_context import WizardContext

ROTATION_SUMMARY_KEY = "setup_summary.rotation"
TOUCH_SUMMARY_KEY = "setup_summary.touch"
NOSLEEP_SUMMARY_KEY = "setup_summary.nosleep"
AUTOLOGIN_SUMMARY_KEY = "setup_summary.autologin"
RUSTDESK_SUMMARY_KEY = "setup_summary.rustdesk"
WEBAPP_SUMMARY_KEY = "setup_summary.webapp"
VIDEO_SUMMARY_KEY = "setup_summary.video"
TOTEM_REGISTRATION_SUMMARY_KEY = "setup_summary.totem_registration"

TOUCH_NOT_DETECTED = "not-detected"
TOUCH_NOT_NEEDED = "not-needed"
TOUCH_UPDATED = "updated"

TOTEM_REGISTRATION_SKIPPED = "skipped"
TOTEM_REGISTRATION_REGISTERED = "registered"

_PROJECT_SELECTION_STEP_ID = "project-kiosk"
_ROTATION_LABELS = {
    "none": "no rotation",
    "clockwise": "clockwise",
    "counterclockwise": "counterclockwise",
}


@dataclass(frozen=True)
class RotationSummary:
    choice_id: str
    output: str
    applied_live: bool


@dataclass(frozen=True)
class TouchSummary:
    outcome: str
    rotation_label: str | None = None


@dataclass(frozen=True)
class RustDeskSummary:
    rustdesk_id: str


@dataclass(frozen=True)
class WebAppSummary:
    repo_ref: str
    source_subdir: str
    artifact_dir: str
    app_dir: str
    launcher_path: str
    server_url: str
    log_tail_command: str
    heartbeat_log_tail_command: str


@dataclass(frozen=True)
class VideoSummary:
    shared_url: str
    file_name: str
    video_path: str
    launcher_path: str


@dataclass(frozen=True)
class TotemRegistrationSummary:
    status: str
    machine_name: str | None = None
    totem_name: str | None = None
    detail: str | None = None


def render_setup_summary(context: WizardContext) -> str:
    lines = ["Done: setup summary", ""]
    state = context.state

    rotation = state.get(ROTATION_SUMMARY_KEY)
    if isinstance(rotation, RotationSummary):
        lines.append(_checked(_format_rotation(rotation)))

    touch = state.get(TOUCH_SUMMARY_KEY)
    if isinstance(touch, TouchSummary):
        lines.append(_checked(_format_touch(touch)))

    if state.get(NOSLEEP_SUMMARY_KEY):
        lines.append(_checked("Screen blanking and sleep were disabled"))

    if state.get(AUTOLOGIN_SUMMARY_KEY):
        lines.append(
            _checked(
                "Desktop autologin was enabled for user "
                f"{context.host.user()}; the account password still works for SSH and sudo"
            )
        )

    rustdesk = state.get(RUSTDESK_SUMMARY_KEY)
    if isinstance(rustdesk, RustDeskSummary):
        lines.append(
            _checked(
                "RustDesk unattended access was installed and configured with ID "
                f"{rustdesk.rustdesk_id}"
            )
        )

    selection = context.answer(_PROJECT_SELECTION_STEP_ID)
    project_type = getattr(selection, "project_type", None)
    if project_type:
        lines.append(_checked(f"Project selected: {project_type}"))

    webapp = state.get(WEBAPP_SUMMARY_KEY)
    if isinstance(webapp, WebAppSummary):
        lines.extend(
            [
                _checked(f"Downloaded the webapp from {_format_webapp_source(webapp)}"),
                _checked(f"Found build output in {webapp.artifact_dir}/"),
                _checked(f"Deployed the webapp to {webapp.app_dir}"),
                _checked(f"Wrote the kiosk launcher to {webapp.launcher_path}"),
                _checked("Configured labwc autostart to launch the kiosk on the next graphical login"),
                _checked(f"Configured the local server to serve the app on {webapp.server_url}"),
                _checked("Configured Chromium kiosk mode for the deployed app"),
                _checked("Configured automatic mouse hide after idle"),
                _checked(f"Server logs: {webapp.log_tail_command}"),
                _checked(f"Heartbeat logs: {webapp.heartbeat_log_tail_command}"),
            ]
        )

    video = state.get(VIDEO_SUMMARY_KEY)
    if isinstance(video, VideoSummary):
        lines.extend(
            [
                _checked(f"Downloaded the video from {video.shared_url}"),
                _checked(f"Deployed the video file to {video.video_path}"),
                _checked(f"Wrote the video launcher to {video.launcher_path}"),
                _checked(
                    "Configured labwc autostart to launch the video on the next graphical login"
                ),
                _checked("Configured mpv for fullscreen looping playback"),
            ]
        )

    registration = state.get(TOTEM_REGISTRATION_SUMMARY_KEY)
    if isinstance(registration, TotemRegistrationSummary):
        lines.append(_checked(_format_totem_registration(registration)))

    return "\n".join(lines)


def _format_rotation(summary: RotationSummary) -> str:
    label = _ROTATION_LABELS.get(summary.choice_id, summary.choice_id)
    if summary.applied_live:
        return (
            f"Screen rotation set to {label} on {summary.output} and applied live; "
            "it will persist on future graphical logins"
        )
    return (
        f"Screen rotation set to {label} on {summary.output}; "
        "it will apply on the next graphical login"
    )


def _format_touch(summary: TouchSummary) -> str:
    if summary.outcome == TOUCH_NOT_DETECTED:
        return "No touch screen detected, so no touch mapping changes were needed"
    if summary.outcome == TOUCH_NOT_NEEDED:
        return (
            "Touch screen detected, but no mapping changes were needed because the "
            "screen is not rotated"
        )
    if summary.outcome == TOUCH_UPDATED:
        rotation_label = summary.rotation_label or "the selected rotation"
        return f"Touch mapping was updated to match {rotation_label}"
    return summary.outcome


def _format_webapp_source(summary: WebAppSummary) -> str:
    if not summary.source_subdir:
        return summary.repo_ref
    return f"{summary.repo_ref} (subdirectory: {summary.source_subdir}/)"


def _format_totem_registration(summary: TotemRegistrationSummary) -> str:
    if summary.status == TOTEM_REGISTRATION_SKIPPED:
        return "Totem registration was skipped"

    if summary.status == TOTEM_REGISTRATION_REGISTERED:
        if summary.totem_name and summary.machine_name:
            message = (
                f'Registered totem "{summary.totem_name}" for machine '
                f"{summary.machine_name}."
            )
        elif summary.machine_name:
            message = f"Registered the totem for machine {summary.machine_name}."
        else:
            message = "Registered the totem."
        if summary.detail:
            return f"{message} {summary.detail}"
        return message

    return summary.status


def _checked(message: str) -> str:
    return f"- [x] {message}"

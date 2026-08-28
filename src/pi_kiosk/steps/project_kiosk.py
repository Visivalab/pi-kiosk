from __future__ import annotations

from dataclasses import dataclass

from pi_kiosk.choice import Choice
from pi_kiosk.host import Host, VideoSource, WebAppSource
from pi_kiosk.steps.kiosk_common import NEXT_ACTION_PROMPT
from pi_kiosk.steps.video_kiosk import VideoKioskStep
from pi_kiosk.steps.webapp_kiosk import WebAppKioskStep
from pi_kiosk.ui import UI

TYPE_OF_PROJECT_PROMPT = "Type of project"
WEBAPP = "webapp"
VIDEO = "video"
PROJECT_TYPE_CHOICES = [
    Choice(id=WEBAPP, label="Webapp"),
    Choice(id=VIDEO, label="Video"),
]


@dataclass(frozen=True)
class ProjectSelection:
    project_type: str
    source: WebAppSource | VideoSource


class ProjectKioskStep:
    id = "project-kiosk"
    title = TYPE_OF_PROJECT_PROMPT
    choices = PROJECT_TYPE_CHOICES
    interactive = True

    def __init__(
        self,
        *,
        prompt_for_next_action: bool = True,
        webapp_step: WebAppKioskStep | None = None,
        video_step: VideoKioskStep | None = None,
    ) -> None:
        self._steps = {
            WEBAPP: webapp_step or WebAppKioskStep(prompt_for_next_action=prompt_for_next_action),
            VIDEO: video_step or VideoKioskStep(prompt_for_next_action=prompt_for_next_action),
        }
        self._last_project_type: str | None = None

    def ask(self, ui: UI) -> ProjectSelection:
        project_type = ui.choose(self.title, list(self.choices))
        source = self._steps[project_type].ask(ui)
        return ProjectSelection(project_type=project_type, source=source)

    def apply(self, host: Host, selection: ProjectSelection) -> str:
        self._last_project_type = selection.project_type
        return self._steps[selection.project_type].apply(host, selection.source)

    def next_action_prompt(self) -> str:
        return self._current_step().next_action_prompt()

    def next_action_choices(self) -> list[Choice]:
        return self._current_step().next_action_choices()

    def perform_next_action(self, host: Host, action: str) -> str:
        return self._current_step().perform_next_action(host, action)

    def selected_project_type(self) -> str:
        if self._last_project_type is None:
            raise RuntimeError("Project kiosk step has not run yet.")
        return self._last_project_type

    def _current_step(self) -> WebAppKioskStep | VideoKioskStep:
        if self._last_project_type is None:
            raise RuntimeError("Project kiosk step has not run yet.")
        return self._steps[self._last_project_type]

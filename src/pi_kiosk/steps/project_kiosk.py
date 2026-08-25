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
        webapp_step: WebAppKioskStep | None = None,
        video_step: VideoKioskStep | None = None,
    ) -> None:
        self._steps = {
            WEBAPP: webapp_step or WebAppKioskStep(),
            VIDEO: video_step or VideoKioskStep(),
        }

    def ask(self, ui: UI) -> ProjectSelection:
        project_type = ui.choose(self.title, list(self.choices))
        source = self._steps[project_type].ask(ui)
        return ProjectSelection(project_type=project_type, source=source)

    def apply(self, host: Host, selection: ProjectSelection) -> str:
        return self._steps[selection.project_type].apply(host, selection.source)

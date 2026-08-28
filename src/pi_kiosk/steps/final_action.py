from __future__ import annotations

from pi_kiosk.host import Host
from pi_kiosk.steps.project_kiosk import ProjectKioskStep
from pi_kiosk.ui import UI


class FinalActionStep:
    id = "next-action"
    title = "Choose what to do next."
    choices = ()
    interactive = True

    def __init__(self, project_step: ProjectKioskStep) -> None:
        self._project_step = project_step

    def ask(self, ui: UI) -> str:
        return ui.choose(
            self._project_step.next_action_prompt(),
            self._project_step.next_action_choices(),
        )

    def apply(self, host: Host, action: str) -> str:
        return self._project_step.perform_next_action(host, action)

from __future__ import annotations

from pi_kiosk.host import Host
from pi_kiosk.steps.project_kiosk import ProjectKioskStep
from pi_kiosk.totem_registration import TotemRegistrar, TotemRegistrationRequest
from pi_kiosk.ui import UI

REGISTER_TOTEM_PROMPT = "Register this totem now?"


class RegisterTotemStep:
    id = "register-totem"
    title = REGISTER_TOTEM_PROMPT
    choices = ()
    interactive = True

    def __init__(
        self,
        registrar: TotemRegistrar | None = None,
        project_step: ProjectKioskStep | None = None,
    ) -> None:
        self._registrar = registrar or TotemRegistrar()
        self._project_step = project_step

    def ask(self, ui: UI) -> TotemRegistrationRequest | None:
        if not ui.confirm(self.title, default=True):
            return None
        totem_type = None
        if self._project_step is not None:
            totem_type = self._project_step.selected_project_type()
        return self._registrar.ask(
            ui,
            totem_type=totem_type,
        )

    def apply(self, host: Host, registration: TotemRegistrationRequest | None) -> str:
        if registration is None:
            return "Done: skipped totem registration."
        return self._registrar.register(host, registration)

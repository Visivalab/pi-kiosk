from __future__ import annotations

import os
from dataclasses import dataclass

from pi_kiosk.choice import Choice
from pi_kiosk.errors import UserFacingError
from pi_kiosk.host import Host, TotemStatusReporterConfig
from pi_kiosk.totem_status import derive_status_url
from pi_kiosk.ui import UI

REGISTER_TOTEM_URL = "http://72.62.59.66:8083/register-totem"
REGISTER_TOTEM_TOKEN = "76cf38119e7a1822abd6935f76583ef1e97ee7fb23a72d39"

TOTEM_TYPE_PROMPT = "Totem type"
TOTEM_NAME_PROMPT = "Totem name"
TOTEM_DESCRIPTION_PROMPT = "Totem description"
TOTEM_LOCATION_PROMPT = "Totem location"
TOTEM_TYPE_CHOICES = [
    Choice(id="webapp", label="Webapp"),
    Choice(id="video", label="Video"),
]


@dataclass(frozen=True)
class TotemRegistrationConfig:
    endpoint_url: str
    token: str


@dataclass(frozen=True)
class TotemRegistrationRequest:
    totem_type: str
    totem_name: str
    description: str
    location: str


def default_config() -> TotemRegistrationConfig | None:
    endpoint_url = os.environ.get("PI_KIOSK_REGISTER_TOTEM_URL", REGISTER_TOTEM_URL).strip()
    token = os.environ.get("PI_KIOSK_REGISTER_TOTEM_TOKEN", REGISTER_TOTEM_TOKEN).strip()
    if not endpoint_url or not token:
        return None
    return TotemRegistrationConfig(
        endpoint_url=endpoint_url,
        token=token,
    )


class TotemRegistrar:
    def __init__(self, config: TotemRegistrationConfig | None = None) -> None:
        self._config = config

    def config(self) -> TotemRegistrationConfig | None:
        return self._config if self._config is not None else default_config()

    def ask(
        self,
        ui: UI,
        *,
        totem_type: str | None = None,
    ) -> TotemRegistrationRequest:
        resolved_totem_type = totem_type or ui.choose(TOTEM_TYPE_PROMPT, list(TOTEM_TYPE_CHOICES))
        resolved_totem_name = _ask_required(ui, TOTEM_NAME_PROMPT)
        resolved_description = _ask_optional(ui, TOTEM_DESCRIPTION_PROMPT)
        resolved_location = _ask_optional(ui, TOTEM_LOCATION_PROMPT)

        return TotemRegistrationRequest(
            totem_type=resolved_totem_type,
            totem_name=resolved_totem_name,
            description=resolved_description,
            location=resolved_location,
        )

    def register(self, host: Host, registration: TotemRegistrationRequest) -> str:
        config = self.config()
        if config is None:
            raise UserFacingError("Totem registration is not configured.")

        machine_name = host.machine_name().strip()
        if not machine_name:
            raise UserFacingError("Could not determine the machine name for this device.")

        connection = host.connection_details()
        host.register_totem(
            config.endpoint_url,
            config.token,
            machine_name,
            registration.totem_type,
            registration.totem_name,
            registration.description,
            registration.location,
            connection,
        )
        status_endpoint_url = derive_status_url(config.endpoint_url)
        if status_endpoint_url:
            warning = host.install_totem_status_reporter(
                TotemStatusReporterConfig(
                    endpoint_url=status_endpoint_url,
                    token=config.token,
                    totem_id=machine_name,
                    totem_type=registration.totem_type,
                    desktop_user=host.user(),
                )
            )
            if warning:
                return (
                    f"Done: totem registered for machine {machine_name}. "
                    f"{warning}"
                )
            return (
                f"Done: totem registered for machine {machine_name}. "
                "Hourly status reporter installed."
            )
        return (
            f"Done: totem registered for machine {machine_name}. "
            "Hourly status reporter was not installed because no status endpoint is configured."
        )


def _ask_required(ui: UI, prompt: str) -> str:
    while True:
        value = ui.prompt(prompt).strip()
        if value:
            return value
        ui.warn(f"{prompt} cannot be empty.")


def _ask_optional(ui: UI, prompt: str) -> str:
    return ui.prompt(prompt).strip()

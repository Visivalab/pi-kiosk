from __future__ import annotations

import os
from dataclasses import dataclass

from pi_kiosk.errors import UserFacingError
from pi_kiosk.host import Host
from pi_kiosk.ui import UI

REGISTER_TOTEM_URL = "http://72.62.59.66:8083/register-totem"
REGISTER_TOTEM_TOKEN = "76cf38119e7a1822abd6935f76583ef1e97ee7fb23a72d39"

TOTEM_NAME_PROMPT = "Totem name"
TOTEM_DESCRIPTION_PROMPT = "Totem description"
TOTEM_LOCATION_PROMPT = "Totem location"


@dataclass(frozen=True)
class TotemRegistrationConfig:
    endpoint_url: str
    token: str


@dataclass(frozen=True)
class TotemRegistrationRequest:
    totem_name: str
    description: str
    location: str


def default_config() -> TotemRegistrationConfig | None:
    endpoint_url = os.environ.get("PI_KIOSK_REGISTER_TOTEM_URL", REGISTER_TOTEM_URL).strip()
    token = os.environ.get("PI_KIOSK_REGISTER_TOTEM_TOKEN", REGISTER_TOTEM_TOKEN).strip()
    if not endpoint_url or not token:
        return None
    return TotemRegistrationConfig(endpoint_url=endpoint_url, token=token)


class TotemRegistrar:
    def __init__(self, config: TotemRegistrationConfig | None = None) -> None:
        self._config = config

    def ask(self, ui: UI) -> TotemRegistrationRequest:
        return TotemRegistrationRequest(
            totem_name=_ask_required(ui, TOTEM_NAME_PROMPT),
            description=_ask_required(ui, TOTEM_DESCRIPTION_PROMPT),
            location=_ask_required(ui, TOTEM_LOCATION_PROMPT),
        )

    def register(self, host: Host, registration: TotemRegistrationRequest) -> str:
        config = self._config if self._config is not None else default_config()
        if config is None:
            raise UserFacingError("Totem registration is not configured.")

        machine_name = host.machine_name().strip()
        if not machine_name:
            raise UserFacingError("Could not determine the machine name for this device.")

        host.register_totem(
            config.endpoint_url,
            config.token,
            machine_name,
            registration.totem_name,
            registration.description,
            registration.location,
        )
        return f"Done: totem registered for machine {machine_name}."


def _ask_required(ui: UI, prompt: str) -> str:
    while True:
        value = ui.prompt(prompt).strip()
        if value:
            return value
        ui.warn(f"{prompt} cannot be empty.")

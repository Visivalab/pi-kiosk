from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DisplayConfig:
    output: str
    transform: str


DISPLAY_CONFIG_KEY = "display_config"

from __future__ import annotations

from typing import Callable

from pi_kiosk.host import Host
from pi_kiosk.ui import UI


class RustDeskStep:
    id = "rustdesk"
    title = "RustDesk password"
    choices = ()
    interactive = True

    def __init__(self) -> None:
        self._progress: Callable[[str], None] | None = None
        self._last_password: str | None = None

    def ask(self, ui: UI) -> str:
        self._progress = ui.progress
        while True:
            password = ui.secret(self.title).strip()
            if password:
                self._last_password = password
                return password
            ui.warn("RustDesk password cannot be empty.")

    def apply(self, host: Host, password: str) -> str:
        progress = self._progress or (lambda _message: None)
        install = host.install_rustdesk(password, progress=progress)
        return (
            "Done: RustDesk installed and configured. "
            f"ID: {install.rustdesk_id}"
        )

    def last_password(self) -> str | None:
        return self._last_password

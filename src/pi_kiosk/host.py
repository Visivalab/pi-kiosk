from dataclasses import dataclass
from typing import Callable
from typing import Protocol


@dataclass(frozen=True)
class WebAppDeployment:
    repo_ref: str
    app_dir: str
    artifact_dir: str


@dataclass(frozen=True)
class WebAppSource:
    repo_ref: str
    subdir: str = ""


class Host(Protocol):
    """System port. Production talks to a Pi; tests use an in-memory fake."""

    def home(self) -> str: ...

    def user(self) -> str: ...

    def is_raspberry_pi(self) -> bool: ...

    def is_root(self) -> bool: ...

    def exists(self, path: str) -> bool: ...

    def mkdir(self, path: str) -> None: ...

    def read_file(self, path: str) -> str: ...

    def write_file(self, path: str, content: str) -> None: ...

    def detect_wayland_output(self) -> str | None: ...

    def run(self, argv: list[str], check: bool = True) -> object: ...

    def run_in_desktop_session(self, argv: list[str], check: bool = True) -> object: ...

    def deploy_webapp(
        self,
        source: WebAppSource,
        artifact_dirs: tuple[str, ...],
        progress: Callable[[str], None] | None = None,
    ) -> WebAppDeployment: ...

    def chromium_command(self) -> str | None: ...

    def launch_kiosk_now(self, launcher: str) -> None: ...

    def touchscreen_present(self) -> bool: ...

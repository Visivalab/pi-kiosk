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


@dataclass(frozen=True)
class VideoDeployment:
    video_path: str
    file_name: str


@dataclass(frozen=True)
class VideoSource:
    shared_url: str
    download_url: str


@dataclass(frozen=True)
class RustDeskInstall:
    rustdesk_id: str
    asset_name: str


@dataclass(frozen=True)
class TotemStatusReporterConfig:
    endpoint_url: str
    token: str
    totem_id: str
    totem_type: str
    desktop_user: str


@dataclass(frozen=True)
class TotemConnectionDetails:
    rustdesk_id: str | None
    rustdesk_password: str | None
    ssh_user: str
    ssh_port: int
    ip_address: str | None
    ip_addresses: tuple[str, ...]


class Host(Protocol):
    """System port. Production talks to a Pi; tests use an in-memory fake."""

    def home(self) -> str: ...

    def user(self) -> str: ...

    def machine_name(self) -> str: ...

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

    def deploy_video(
        self,
        source: VideoSource,
        progress: Callable[[str], None] | None = None,
    ) -> VideoDeployment: ...

    def chromium_command(self) -> str | None: ...

    def mpv_command(self) -> str | None: ...

    def wtype_command(self) -> str | None: ...

    def swayidle_command(self) -> str | None: ...

    def ensure_packages_installed(self, packages: tuple[str, ...]) -> None: ...

    def launch_kiosk_now(self, launcher: str) -> None: ...

    def launch_webapp_server_now(self, launcher: str) -> None: ...

    def launch_video_now(self, launcher: str) -> None: ...

    def reboot(self) -> None: ...

    def touchscreen_present(self) -> bool: ...

    def install_rustdesk(
        self,
        password: str,
        progress: Callable[[str], None] | None = None,
    ) -> RustDeskInstall: ...

    def connection_details(
        self,
        rustdesk_password: str | None = None,
    ) -> TotemConnectionDetails: ...

    def register_totem(
        self,
        endpoint_url: str,
        token: str,
        machine_name: str,
        totem_type: str,
        totem_name: str,
        description: str,
        location: str,
        connection: TotemConnectionDetails,
    ) -> None: ...

    def install_totem_status_reporter(
        self,
        config: TotemStatusReporterConfig,
    ) -> str | None: ...

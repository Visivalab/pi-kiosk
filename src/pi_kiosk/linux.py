from __future__ import annotations

import getpass
import json
import os
import pwd
import shlex
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Callable
from urllib import error, request

from pi_kiosk.detect import looks_like_raspberry_pi
from pi_kiosk.errors import UserFacingError
from pi_kiosk.host import RustDeskInstall, WebAppDeployment, WebAppSource


class NeedSudoUser(RuntimeError):
    """The tool must know which desktop user's home to modify."""


class LinuxHost:
    """Talks to the real machine. Keep this thin; logic lives in the steps."""

    def home(self) -> str:
        return str(Path(pwd.getpwnam(self.user()).pw_dir))

    def user(self) -> str:
        sudo_user = os.environ.get("SUDO_USER")
        if sudo_user:
            return sudo_user
        if self.is_root():
            raise NeedSudoUser(
                "Run this tool with sudo from the desktop user account. "
                "Nothing was changed."
            )
        return getpass.getuser()

    def is_raspberry_pi(self) -> bool:
        return looks_like_raspberry_pi(
            model=_read_device_tree_model(),
            has_rpi_issue=Path("/etc/rpi-issue").is_file(),
        )

    def is_root(self) -> bool:
        return os.geteuid() == 0

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def mkdir(self, path: str) -> None:
        directory = Path(path)
        directory.mkdir(parents=True, exist_ok=True)
        self._own_within_home(directory)

    def read_file(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._own_within_home(target.parent)
        target.write_text(content, encoding="utf-8")
        if target.name == "autostart":
            target.chmod(0o755)
        self._own(target)

    def detect_wayland_output(self) -> str | None:
        result = self.run_in_desktop_session(["wlr-randr"], check=False)
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            if line and not line[0].isspace():
                return line.split()[0]
        return None

    def run(self, argv: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(argv, check=check, text=True)

    def run_in_desktop_session(
        self,
        argv: list[str],
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        env = self._desktop_session_env()
        if env is None:
            result = subprocess.CompletedProcess(
                args=list(argv),
                returncode=1,
                stdout="",
                stderr="No desktop Wayland session detected.",
            )
            if check:
                raise subprocess.CalledProcessError(
                    result.returncode,
                    argv,
                    output=result.stdout,
                    stderr=result.stderr,
                )
            return result

        if self.is_root():
            command = ["sudo", "-u", self.user(), "env"]
            command.extend(f"{name}={value}" for name, value in env.items())
            command.extend(argv)
            return subprocess.run(
                command,
                check=check,
                text=True,
                capture_output=True,
            )

        merged_env = os.environ.copy()
        merged_env.update(env)
        return subprocess.run(
            argv,
            check=check,
            text=True,
            capture_output=True,
            env=merged_env,
        )

    def deploy_webapp(
        self,
        source: WebAppSource,
        artifact_dirs: tuple[str, ...],
        progress: Callable[[str], None] | None = None,
    ) -> WebAppDeployment:
        self._report_progress(progress, "Resolving GitHub repo")
        app_root = Path(self.home()) / ".local" / "share" / "pi-kiosk" / "webapp"
        current_dir = app_root / "current"
        app_root.mkdir(parents=True, exist_ok=True)
        self._own_within_home(app_root)

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            self._report_progress(progress, "Downloading webapp archive")
            extracted_root = self._download_github_archive(source.repo_ref, temp_root)
            self._report_progress(progress, "Extracting webapp files")
            source_root = self._resolve_source_root(extracted_root, source)
            artifact_path = self._find_artifact_dir(source_root, artifact_dirs)
            if artifact_path is None:
                names = " or ".join(f"{name}/" for name in artifact_dirs)
                raise UserFacingError(
                    f"Repository {source.repo_ref} did not contain {names} "
                    f"in {source.subdir or 'the repo root'}. "
                    "Commit the built webapp and run the wizard again."
                )
            stage_dir = app_root / "next"
            if stage_dir.exists():
                shutil.rmtree(stage_dir)
            stage_dir.mkdir(parents=True, exist_ok=True)
            self._report_progress(progress, "Deploying build output")
            self._copy_directory_contents(artifact_path, stage_dir)
            if current_dir.exists():
                shutil.rmtree(current_dir)
            stage_dir.replace(current_dir)

        self._own_tree(current_dir)
        return WebAppDeployment(
            repo_ref=source.repo_ref,
            app_dir=str(current_dir),
            artifact_dir=artifact_path.name,
        )

    def chromium_command(self) -> str | None:
        for candidate in ("chromium-browser", "chromium"):
            found = shutil.which(candidate)
            if found:
                return found
        return None

    def wtype_command(self) -> str | None:
        return shutil.which("wtype")

    def swayidle_command(self) -> str | None:
        return shutil.which("swayidle")

    def ensure_packages_installed(self, packages: tuple[str, ...]) -> None:
        subprocess.run(
            ["apt-get", "install", "-y", *packages],
            check=True,
            text=True,
        )

    def launch_kiosk_now(self, launcher: str) -> None:
        command = [
            "sh",
            "-lc",
            " ".join(
                [
                    "labwc --reconfigure >/dev/null 2>&1 || true;",
                    "sleep 1;",
                    f"nohup bash {shlex.quote(launcher)} >/dev/null 2>&1 </dev/null &",
                ]
            ),
        ]
        self.run_in_desktop_session(command, check=True)

    def launch_webapp_server_now(self, launcher: str) -> None:
        command = [
            "sh",
            "-lc",
            f"nohup bash {shlex.quote(launcher)} server-only >/dev/null 2>&1 </dev/null &",
        ]
        self.run_in_desktop_session(command, check=True)

    def reboot(self) -> None:
        subprocess.run(["reboot"], check=True, text=True)

    def touchscreen_present(self) -> bool:
        try:
            result = subprocess.run(
                ["libinput", "list-devices"],
                check=False,
                text=True,
                capture_output=True,
            )
        except FileNotFoundError:
            return False
        return _libinput_reports_touch(result.stdout)

    def install_rustdesk(
        self,
        password: str,
        progress: Callable[[str], None] | None = None,
    ) -> RustDeskInstall:
        self._report_progress(progress, "Resolving latest RustDesk release")
        release = self._read_json("https://api.github.com/repos/rustdesk/rustdesk/releases/latest")
        asset = _select_rustdesk_deb_asset(release, self._debian_architecture())

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            package_path = temp_root / asset["name"]

            self._report_progress(progress, "Downloading RustDesk package")
            self._download_file(str(asset["browser_download_url"]), package_path)

            self._report_progress(progress, "Installing RustDesk package")
            subprocess.run(
                ["apt-get", "install", "-fy", str(package_path)],
                check=True,
                text=True,
            )

        self._report_progress(progress, "Configuring RustDesk access")
        self._restart_rustdesk_service()
        rustdesk_id = self._rustdesk_get_id()
        subprocess.run(["rustdesk", "--password", password], check=True, text=True)
        self._restart_rustdesk_service()

        return RustDeskInstall(
            rustdesk_id=rustdesk_id,
            asset_name=str(asset["name"]),
        )

    def _own(self, path: Path) -> None:
        if not self.is_root():
            return
        try:
            info = pwd.getpwnam(self.user())
        except KeyError:
            return
        os.chown(path, info.pw_uid, info.pw_gid)

    def _own_within_home(self, path: Path) -> None:
        home = Path(self.home())
        current = path
        while current == home or home in current.parents:
            self._own(current)
            if current == home:
                break
            current = current.parent

    def _desktop_session_env(self) -> dict[str, str] | None:
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR")
        wayland_display = os.environ.get("WAYLAND_DISPLAY")

        if self.is_root():
            user_info = pwd.getpwnam(self.user())
            runtime_dir = runtime_dir or f"/run/user/{user_info.pw_uid}"

        if not runtime_dir:
            return None

        runtime_path = Path(runtime_dir)
        if not runtime_path.is_dir():
            return None

        if not wayland_display:
            sockets = sorted(runtime_path.glob("wayland-*"))
            if not sockets:
                return None
            wayland_display = sockets[0].name

        return {
            "XDG_RUNTIME_DIR": str(runtime_path),
            "WAYLAND_DISPLAY": wayland_display,
        }

    def _download_github_archive(self, repo_ref: str, target_dir: Path) -> Path:
        owner, repo = repo_ref.split("/", 1)
        default_branch = self._github_default_branch(owner, repo)
        archive_url = (
            f"https://codeload.github.com/{owner}/{repo}/tar.gz/refs/heads/{default_branch}"
        )
        archive_path = target_dir / "repo.tar.gz"
        self._download_file(archive_url, archive_path)
        with tarfile.open(archive_path, "r:gz") as bundle:
            bundle.extractall(target_dir)
        roots = [entry for entry in target_dir.iterdir() if entry.is_dir()]
        if not roots:
            raise UserFacingError(f"Downloaded archive for {repo_ref} was empty.")
        return roots[0]

    def _github_default_branch(self, owner: str, repo: str) -> str:
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        payload = self._read_json(api_url)
        default_branch = payload.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise UserFacingError(
                f"Could not determine the default branch for {owner}/{repo}."
            )
        return default_branch

    def _read_json(self, url: str) -> dict[str, object]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "pi-kiosk-setup",
        }
        req = request.Request(url, headers=headers)
        try:
            with request.urlopen(req) as response:
                return json.load(response)
        except error.HTTPError as exc:
            if exc.code == 404:
                raise UserFacingError(
                    "GitHub repo was not found or is not public. "
                    "Use a public repo for this version of the wizard."
                ) from exc
            raise UserFacingError(f"GitHub API request failed with HTTP {exc.code}.") from exc
        except error.URLError as exc:
            raise UserFacingError(
                f"Could not reach GitHub to download the webapp: {exc.reason}."
            ) from exc

    def _download_file(self, url: str, target: Path) -> None:
        headers = {"User-Agent": "pi-kiosk-setup"}
        req = request.Request(url, headers=headers)
        try:
            with request.urlopen(req) as response, target.open("wb") as stream:
                shutil.copyfileobj(response, stream)
        except error.HTTPError as exc:
            raise UserFacingError(f"Failed to download the webapp archive (HTTP {exc.code}).") from exc
        except error.URLError as exc:
            raise UserFacingError(
                f"Could not download the webapp archive: {exc.reason}."
            ) from exc

    def _find_artifact_dir(self, root: Path, artifact_dirs: tuple[str, ...]) -> Path | None:
        for name in artifact_dirs:
            candidate = root / name
            if candidate.is_dir():
                return candidate
        return None

    def _resolve_source_root(self, extracted_root: Path, source: WebAppSource) -> Path:
        if not source.subdir:
            return extracted_root

        relative = Path(source.subdir)
        if relative.is_absolute() or ".." in relative.parts:
            raise UserFacingError("Webapp subdirectory must stay inside the repo.")

        source_root = extracted_root / relative
        if not source_root.is_dir():
            raise UserFacingError(
                f"Subdirectory {source.subdir} was not found in {source.repo_ref}."
            )
        return source_root

    def _copy_directory_contents(self, source: Path, target: Path) -> None:
        for child in source.iterdir():
            destination = target / child.name
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)

    def _own_tree(self, root: Path) -> None:
        self._own_within_home(root)
        for child in root.rglob("*"):
            self._own(child)

    def _report_progress(
        self,
        progress: Callable[[str], None] | None,
        message: str,
    ) -> None:
        if progress is not None:
            progress(message)

    def _debian_architecture(self) -> str:
        result = subprocess.run(
            ["dpkg", "--print-architecture"],
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout.strip()

    def _restart_rustdesk_service(self) -> None:
        subprocess.run(
            ["systemctl", "restart", "rustdesk"],
            check=False,
            text=True,
        )

    def _rustdesk_get_id(self) -> str:
        result = subprocess.run(
            ["rustdesk", "--get-id"],
            check=True,
            text=True,
            capture_output=True,
        )
        rustdesk_id = result.stdout.strip()
        if not rustdesk_id:
            raise UserFacingError("RustDesk did not return an ID after installation.")
        return rustdesk_id


def _read_device_tree_model() -> str | None:
    for candidate in (
        Path("/proc/device-tree/model"),
        Path("/sys/firmware/devicetree/base/model"),
    ):
        try:
            raw = candidate.read_bytes()
        except OSError:
            continue
        return raw.split(b"\0", 1)[0].decode("utf-8", errors="replace")
    return None


def _libinput_reports_touch(stdout: str) -> bool:
    for line in stdout.splitlines():
        if line.lstrip().startswith("Capabilities:") and "touch" in line.lower():
            return True
    return False


def _select_rustdesk_deb_asset(release: dict[str, object], arch: str) -> dict[str, str]:
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise UserFacingError("RustDesk release metadata did not include assets.")

    suffixes = _rustdesk_asset_suffixes(arch)
    for suffix in suffixes:
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name")
            url = asset.get("browser_download_url")
            if isinstance(name, str) and isinstance(url, str) and name.endswith(suffix):
                return {"name": name, "browser_download_url": url}

    raise UserFacingError(
        f"No supported RustDesk .deb package was found for architecture {arch}."
    )


def _rustdesk_asset_suffixes(arch: str) -> tuple[str, ...]:
    mapping = {
        "arm64": ("aarch64.deb",),
        "armhf": ("armv7-sciter.deb", "armv7.deb"),
        "amd64": ("x86_64.deb", "amd64.deb"),
    }
    return mapping.get(arch, ())

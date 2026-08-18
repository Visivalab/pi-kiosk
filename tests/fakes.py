from dataclasses import dataclass, field


@dataclass
class CommandResult:
    argv: list[str]
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class FakeHost:
    """In-memory host. Tests never touch the real machine."""

    def __init__(
        self,
        *,
        home: str = "/home/pi",
        user: str = "pi",
        files: dict[str, str] | None = None,
        wayland_output: str | None = "HDMI-A-1",
        raspberry_pi: bool = True,
        root: bool = True,
    ) -> None:
        self.home_dir = home
        self.username = user
        self.files: dict[str, str] = dict(files or {})
        self.wayland_output = wayland_output
        self.raspberry_pi = raspberry_pi
        self.root = root
        self.commands: list[list[str]] = []
        self.directories: set[str] = set()

    def home(self) -> str:
        return self.home_dir

    def user(self) -> str:
        return self.username

    def is_raspberry_pi(self) -> bool:
        return self.raspberry_pi

    def is_root(self) -> bool:
        return self.root

    def exists(self, path: str) -> bool:
        if path in self.files:
            return True
        return any(entry.startswith(path.rstrip("/") + "/") for entry in self.files)

    def mkdir(self, path: str) -> None:
        self.directories.add(path)

    def read_file(self, path: str) -> str:
        try:
            return self.files[path]
        except KeyError as exc:
            raise FileNotFoundError(path) from exc

    def write_file(self, path: str, content: str) -> None:
        parent = path.rsplit("/", 1)[0]
        if parent:
            self.directories.add(parent)
        self.files[path] = content

    def detect_wayland_output(self) -> str | None:
        return self.wayland_output

    def run(self, argv: list[str], check: bool = True) -> CommandResult:
        self.commands.append(list(argv))
        return CommandResult(argv=list(argv), returncode=0)

from pi_kiosk.choice import Choice
from pi_kiosk.files import read_or_empty, upsert_marked_block
from pi_kiosk.host import Host
from pi_kiosk.ui import UI

ROTATION_CHOICES = (
    Choice("none", "No rotation"),
    Choice("clockwise", "Rotate clockwise (90°)"),
    Choice("counterclockwise", "Rotate counterclockwise (90°)"),
)

_TRANSFORMS = {
    "none": "0",
    "clockwise": "90",
    "counterclockwise": "270",
}

_LABELS = {choice.id: choice.label for choice in ROTATION_CHOICES}

BEGIN = "# pi-kiosk-setup:rotation-begin"
END = "# pi-kiosk-setup:rotation-end"
DEFAULT_OUTPUT = "HDMI-A-1"


def transform_for(choice_id: str) -> str:
    try:
        return _TRANSFORMS[choice_id]
    except KeyError as exc:
        raise ValueError(f"unknown rotation choice: {choice_id}") from exc


class RotationStep:
    id = "rotation"
    title = "Screen rotation"
    choices = ROTATION_CHOICES

    def ask(self, ui: UI) -> str:
        return ui.choose(self.title, list(self.choices))

    def apply(self, host: Host, choice_id: str) -> str:
        transform = transform_for(choice_id)
        output = host.detect_wayland_output() or DEFAULT_OUTPUT
        command = f"wlr-randr --output {output} --transform {transform}"

        path = f"{host.home()}/.config/labwc/autostart"
        host.mkdir(f"{host.home()}/.config/labwc")
        updated = upsert_marked_block(
            read_or_empty(host, path),
            BEGIN,
            END,
            command,
        )
        host.write_file(path, updated)

        label = _LABELS[choice_id]
        return (
            f"Done: screen rotation set to {label.lower()} "
            f"({command}). It applies on the next graphical login."
        )

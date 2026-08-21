from __future__ import annotations

from pi_kiosk.files import normalize_labwc_rc_xml, read_or_empty
from pi_kiosk.host import Host
from pi_kiosk.steps.rotation import BEGIN as ROTATION_BEGIN
from pi_kiosk.steps.rotation import END as ROTATION_END
from pi_kiosk.ui import UI

BEGIN = "<!-- pi-kiosk-setup:touch-begin -->"
END = "<!-- pi-kiosk-setup:touch-end -->"
_RC_XML_HEADER = '<?xml version="1.0"?>\n<labwc_config>\n'
_RC_XML_FOOTER = "</labwc_config>\n"
_TRANSFORM_LABELS = {
    "normal": "no rotation",
    "90": "counterclockwise rotation",
    "180": "180 degree rotation",
    "270": "clockwise rotation",
}
_CALIBRATION_MATRICES = {
    "90": "0 -1 1 1 0 0",
    "180": "-1 0 1 0 -1 1",
    "270": "0 1 0 -1 0 1",
}


class TouchStep:
    id = "touch"
    title = "Touchscreen mapping"
    choices = ()

    def ask(self, ui: UI) -> None:
        return None

    def apply(self, host: Host, answer=None) -> str:
        if not host.touchscreen_present():
            return "Done: no touch screen was detected. Nothing was changed."

        output, transform = _read_rotation_state(host)
        if transform == "normal":
            return (
                "Done: touch screen detected. No mapping needed because the screen is not rotated."
            )

        matrix = _CALIBRATION_MATRICES[transform]
        path = f"{host.home()}/.config/labwc/rc.xml"
        host.mkdir(f"{host.home()}/.config/labwc")
        updated = upsert_touch_block(
            read_or_empty(host, path),
            output=output,
            matrix=matrix,
        )
        host.write_file(path, updated)
        return (
            "Done: touch screen detected. Touch mapping was updated to match "
            f"{_TRANSFORM_LABELS[transform]}."
        )


def _read_rotation_state(host: Host) -> tuple[str, str]:
    path = f"{host.home()}/.config/labwc/autostart"
    content = read_or_empty(host, path)
    if ROTATION_BEGIN not in content or ROTATION_END not in content:
        return "HDMI-A-1", "normal"
    _, rest = content.split(ROTATION_BEGIN, 1)
    block, _ = rest.split(ROTATION_END, 1)
    parts = block.split()
    try:
        output = parts[parts.index("--output") + 1]
        transform = parts[parts.index("--transform") + 1]
    except (ValueError, IndexError):
        return "HDMI-A-1", "normal"
    return output, transform


def touch_block(output: str, matrix: str) -> str:
    return "\n".join(
        [
            "  <touch mapToOutput=\"%s\" />" % output,
            "  <libinput>",
            "    <device category=\"touch\">",
            f"      <calibrationMatrix>{matrix}</calibrationMatrix>",
            "    </device>",
            "  </libinput>",
        ]
    )


def upsert_touch_block(original: str, *, output: str, matrix: str) -> str:
    original = normalize_labwc_rc_xml(original)
    block = f"{BEGIN}\n{touch_block(output, matrix)}\n{END}"
    if not original.strip():
        return f"{_RC_XML_HEADER}{block}\n{_RC_XML_FOOTER}"
    if BEGIN in original and END in original:
        pre, rest = original.split(BEGIN, 1)
        _, post = rest.split(END, 1)
        if post.startswith("\n"):
            post = post[1:]
        return f"{pre}{block}\n{post}"
    closing = "</labwc_config>"
    if closing in original:
        before, after = original.rsplit(closing, 1)
        if before and not before.endswith("\n"):
            before += "\n"
        return f"{before}{block}\n{closing}{after}"
    if original and not original.endswith("\n"):
        original += "\n"
    return f"{original}{block}\n"

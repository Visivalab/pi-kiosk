from pi_kiosk.files import read_or_empty, upsert_marked_block
from pi_kiosk.host import Host
from pi_kiosk.ui import UI

BEGIN = "# pi-kiosk-setup:nosleep-begin"
END = "# pi-kiosk-setup:nosleep-end"
IDLE_GUARD = "wlopm --on '*' >/dev/null 2>&1 || true"


class NoSleepStep:
    id = "nosleep"
    title = "Keep the display awake"
    choices = ()

    def ask(self, ui: UI) -> None:
        return None

    def apply(self, host: Host, answer=None) -> str:
        host.run(["raspi-config", "nonint", "do_blanking", "1"], check=True)

        path = f"{host.home()}/.config/labwc/autostart"
        host.mkdir(f"{host.home()}/.config/labwc")
        updated = upsert_marked_block(
            read_or_empty(host, path),
            BEGIN,
            END,
            IDLE_GUARD,
        )
        host.write_file(path, updated)

        return (
            "Done: screen blanking and sleep are disabled. "
            "The display should stay on after reboot."
        )

from pi_kiosk.host import Host
from pi_kiosk.ui import UI


class AutologinStep:
    id = "autologin"
    title = "Desktop autologin"
    choices = ()

    def ask(self, ui: UI) -> None:
        return None

    def apply(self, host: Host, answer=None) -> str:
        host.run(["raspi-config", "nonint", "do_boot_behaviour", "B4"], check=True)
        return (
            "Done: desktop autologin is enabled. "
            "The machine will start the desktop without asking for a password. "
            "The account password still exists for SSH and sudo."
        )

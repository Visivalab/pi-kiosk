from pi_kiosk.host import Host
from pi_kiosk.steps.autologin import AutologinStep
from pi_kiosk.steps.nosleep import NoSleepStep
from pi_kiosk.steps.rotation import RotationStep
from pi_kiosk.steps.touch import TouchStep
from pi_kiosk.steps.webapp_kiosk import WebAppKioskStep
from pi_kiosk.ui import UI


class NotARaspberryPi(RuntimeError):
    """The wizard must not mutate a non-Pi machine."""


class NeedRoot(RuntimeError):
    """raspi-config and system files need root."""


def default_steps():
    return (RotationStep(), TouchStep(), NoSleepStep(), AutologinStep(), WebAppKioskStep())


class Wizard:
    def __init__(self, host: Host, ui: UI, steps=None) -> None:
        self.host = host
        self.ui = ui
        self.steps = tuple(steps) if steps is not None else default_steps()

    @classmethod
    def question_step_ids(cls) -> list[str]:
        return [
            step.id
            for step in default_steps()
            if getattr(step, "interactive", bool(step.choices))
        ]

    def run(self) -> list[str]:
        if not self.host.is_raspberry_pi():
            raise NotARaspberryPi(
                "This tool only configures Raspberry Pi OS. "
                "Nothing was changed on this machine."
            )
        if not self.host.is_root():
            raise NeedRoot("Run this tool with sudo. Nothing was changed.")
        self.host.user()

        reports: list[str] = []
        for step in self.steps:
            answer = step.ask(self.ui)
            report = step.apply(self.host, answer)
            self.ui.info(report)
            reports.append(report)
        return reports

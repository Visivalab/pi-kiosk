from __future__ import annotations

import sys
from typing import TextIO

from pi_kiosk.app import NeedRoot, NotARaspberryPi, Wizard
from pi_kiosk.errors import UserFacingError
from pi_kiosk.host import Host
from pi_kiosk.linux import LinuxHost, NeedSudoUser
from pi_kiosk.terminal_ui import TerminalUI
from pi_kiosk.ui import UI


def main(
    host: Host | None = None,
    ui: UI | None = None,
    stderr: TextIO | None = None,
) -> int:
    stderr = stderr if stderr is not None else sys.stderr
    real_host = host if host is not None else LinuxHost()
    real_ui = ui if ui is not None else TerminalUI()
    try:
        Wizard(real_host, real_ui).run()
    except KeyboardInterrupt:
        return 130
    except NotARaspberryPi as exc:
        print(str(exc), file=stderr)
        return 2
    except (EOFError, NeedRoot, NeedSudoUser, UserFacingError) as exc:
        if isinstance(exc, EOFError):
            print(
                "No terminal input was available for the rotation prompt. "
                "Run this tool from a real terminal. Nothing was changed.",
                file=stderr,
            )
            return 1
        print(str(exc), file=stderr)
        return 1
    return 0

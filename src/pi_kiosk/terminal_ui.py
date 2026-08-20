from __future__ import annotations

import sys
from typing import TextIO

from pi_kiosk.choice import Choice


class TerminalUI:
    def __init__(
        self,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout

    def choose(self, prompt: str, options: list[Choice]) -> str:
        if not options:
            raise ValueError("choose() needs at least one option")

        while True:
            self.stdout.write(f"{prompt}\n")
            for index, option in enumerate(options, start=1):
                self.stdout.write(f"{index}) {option.label}\n")
            self.stdout.write(f"Choose [1-{len(options)}]: ")
            self.stdout.flush()

            raw = self.stdin.readline()
            if raw == "":
                raise EOFError("no rotation choice was provided")
            text = raw.strip()
            if text.isdigit():
                number = int(text)
                if 1 <= number <= len(options):
                    return options[number - 1].id
            self.stdout.write("Invalid choice. Enter a number from the list.\n")
            self.stdout.flush()

    def prompt(self, prompt: str) -> str:
        self.stdout.write(f"{prompt}: ")
        self.stdout.flush()
        raw = self.stdin.readline()
        if raw == "":
            raise EOFError("no text input was provided")
        return raw.strip()

    def info(self, message: str) -> None:
        self.stdout.write(f"{message}\n")
        self.stdout.flush()

    def warn(self, message: str) -> None:
        self.stdout.write(f"WARN: {message}\n")
        self.stdout.flush()

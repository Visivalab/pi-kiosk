from pi_kiosk.choice import Choice


class FakeUI:
    def __init__(self, answers: dict[str, str] | None = None) -> None:
        self.answers = dict(answers or {})
        self.messages: list[str] = []
        self.prompts: list[str] = []

    def choose(self, prompt: str, options: list[Choice]) -> str:
        self.prompts.append(prompt)
        if prompt in self.answers:
            return self.answers[prompt]
        if len(options) == 1:
            return options[0].id
        raise AssertionError(f"no programmed answer for prompt: {prompt!r}")

    def prompt(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt in self.answers:
            return self.answers[prompt]
        raise AssertionError(f"no programmed answer for prompt: {prompt!r}")

    def confirm(self, prompt: str, default: bool = True) -> bool:
        self.prompts.append(prompt)
        if prompt not in self.answers:
            return default
        answer = str(self.answers[prompt]).strip().lower()
        if answer in ("", "y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        raise AssertionError(f"invalid programmed answer for prompt: {prompt!r}")

    def secret(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if prompt in self.answers:
            return self.answers[prompt]
        raise AssertionError(f"no programmed answer for prompt: {prompt!r}")

    def info(self, message: str) -> None:
        self.messages.append(message)

    def progress(self, message: str) -> None:
        self.messages.append(f"[....] {message}")

    def warn(self, message: str) -> None:
        self.messages.append(f"WARN: {message}")

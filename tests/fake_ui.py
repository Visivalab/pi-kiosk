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

    def info(self, message: str) -> None:
        self.messages.append(message)

    def warn(self, message: str) -> None:
        self.messages.append(f"WARN: {message}")

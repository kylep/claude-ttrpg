class EngineError(Exception):
    """Engine failure carrying a stable machine-readable `code` (surfaced in
    the CLI's JSON error output) alongside a human-readable message."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ManualRoll(Exception):
    """Signals that the operator has chosen to roll a physical d20 themselves
    instead of the engine using its RNG. Deliberately NOT an EngineError, so
    guard() does not treat it as a failure: the CLI catches it separately and
    emits a 'here is which die to roll' instruction with a zero exit code.

    Carries what to roll: `die` ("d20"), `count` (1, or 2 for advantage/
    disadvantage), `keep` ("high" | "low" | "one"), the `modifier` to add to
    the natural, and a human `label` for the prompt."""

    def __init__(self, *, die: str, count: int, keep: str, modifier: int, label: str):
        super().__init__(f"manual roll requested: {label}")
        self.die = die
        self.count = count
        self.keep = keep
        self.modifier = modifier
        self.label = label

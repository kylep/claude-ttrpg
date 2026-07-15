class EngineError(Exception):
    """Engine failure carrying a stable machine-readable `code` (surfaced in
    the CLI's JSON error output) alongside a human-readable message."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

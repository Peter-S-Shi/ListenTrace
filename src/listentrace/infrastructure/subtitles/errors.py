from __future__ import annotations


class SubtitleParseError(ValueError):
    def __init__(self, message: str, line_number: int | None = None):
        self.line_number = line_number
        if line_number is not None:
            message = f"line {line_number}: {message}"
        super().__init__(message)

"""What validating an input file reports, like EnergyPlus' scripts/dev/base_hook.py does."""

from dataclasses import dataclass
from enum import IntEnum


class LogLevel(IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3

    def __str__(self) -> str:
        return self.name.capitalize()


@dataclass(frozen=True)
class LogMessage:
    tool: str  # The rule that found it, eg "idd-field-ids"
    loglevel: LogLevel
    message: str
    line_number: int | None = None
    line: str | None = None

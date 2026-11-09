"""What validating an input file reports, like EnergyPlus' scripts/dev/base_hook.py does."""

import json
import os
import sys
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path


class LogLevel(IntEnum):
    INFO = 1
    WARNING = 2
    ERROR = 3

    def __str__(self) -> str:
        return self.name.capitalize()

    def to_gha(self) -> str:
        """The GitHub Actions annotation level."""
        return {LogLevel.INFO: "notice", LogLevel.WARNING: "warning", LogLevel.ERROR: "error"}[self]

    def to_icon(self) -> str:
        """A simple icon for the log level."""
        return {LogLevel.INFO: "ℹ️ ", LogLevel.WARNING: "⚠️ ", LogLevel.ERROR: "❌"}[self]


_BOLD = "\033[1m"
_RESET = "\033[0m"
_COLORS = {LogLevel.INFO: "\033[36m", LogLevel.WARNING: "\033[35m", LogLevel.ERROR: "\033[31m"}  # cyan, magenta, red


def use_color() -> bool:
    """Like most CLIs: NO_COLOR wins, then FORCE_COLOR, then only on a terminal or in GitHub Actions (renders ANSI)."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR") or "GITHUB_ACTIONS" in os.environ:
        return True
    return sys.stdout.isatty()


def _escape_data(text: str) -> str:
    """Escape the message of a GitHub Actions workflow command. % first, or it would escape the others again."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _escape_property(text: str) -> str:
    """Escape a property value (file=, title=) of a workflow command: also : and , which separate properties."""
    return _escape_data(text).replace(":", "%3A").replace(",", "%2C")


@dataclass(frozen=True)
class LogMessage:
    tool: str  # The rule that found it, eg "idd-field-ids"
    loglevel: LogLevel
    message: str
    line_number: int | None = None
    line: str | None = None
    # The validate() methods don't know which file they're in, whoever loaded the file sets it
    filepath: Path | None = None

    def __str__(self) -> str:
        return self.format(color=False)

    def format(self, color: bool = False) -> str:
        """Like clang-tidy: path:line: level: message [tool], then the offending line if any."""

        def style(text: str, *codes: str) -> str:
            return f"{''.join(codes)}{text}{_RESET}" if color else text

        msg = ""
        if self.filepath is not None:
            where = f"{self.filepath}"
            if self.line_number is not None:
                where += f":{self.line_number}"
            msg = f"{where}: "
        msg += style(f"{self.loglevel.name.lower()}: ", _BOLD, _COLORS[self.loglevel])
        msg += f"{self.message} "
        msg += style(f"[{self.tool}]", _BOLD)
        if self.line is not None:
            msg += f"\n    {self.line}"
        return msg

    def to_dict(self) -> dict[str, object]:
        """The keys of LogMessage.to_dict in EnergyPlus' scripts/dev/base_hook.py."""
        fields: dict[str, object] = {
            "tool": self.tool,
            "loglevel": str(self.loglevel),
            "filename": None if self.filepath is None else self.filepath.name,
            "file": None if self.filepath is None else str(self.filepath),
            "line": self.line_number,
            "message": self.message,
        }
        return {key: value for key, value in fields.items() if value is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    def to_github_annotation(self) -> str:
        """A GitHub Actions workflow command, which shows up as an annotation on the PR."""
        safe_message = self.message
        if self.line is not None:
            safe_message += "\n" + self.line
        # The runner decodes only these in the message, see UnescapeData in actions/runner's ActionCommand.cs
        safe_message = _escape_data(safe_message)

        properties = []
        if self.filepath is not None:
            properties.append(f"file={_escape_property(str(self.filepath))}")
            # GitHub needs a line to place it in the file
            properties.append(f"line={self.line_number or 1}")
        properties.append(f"title={_escape_property(self.tool)}")
        return f"::{self.loglevel.to_gha()} {','.join(properties)}::{safe_message}"

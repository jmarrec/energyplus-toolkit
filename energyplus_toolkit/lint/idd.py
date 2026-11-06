"""Lint IDD files: report everything IddFile.validate finds, the file itself isn't changed."""

from __future__ import annotations

import json
from collections import Counter
from enum import Enum
from pathlib import Path

from energyplus_toolkit.input.idd.idd_field import IddFieldParseError
from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.log_message import LogLevel, LogMessage


class OutputFormat(Enum):
    TEXT = "text"
    JSON = "json"


def lint_file(path: Path) -> list[LogMessage]:
    """The messages for this file. One that can't be parsed gets a single error."""
    try:
        idd_file = IddFile.load(path)
    except (ValueError, IddFieldParseError) as exc:
        return [LogMessage(tool="idd-parse", loglevel=LogLevel.ERROR, message=str(exc))]
    return idd_file.validate()


def _text(path: Path, msg: LogMessage) -> str:
    where = str(path) if msg.line_number is None else f"{path}:{msg.line_number}"
    return f"{where}: {msg.loglevel.name.lower()}: [{msg.tool}] {msg.message}"


def _json(path: Path, msg: LogMessage) -> str:
    """The keys of LogMessage.to_dict in EnergyPlus' scripts/dev/base_hook.py."""
    fields: dict[str, object] = {
        "tool": msg.tool,
        "loglevel": str(msg.loglevel),
        "filename": path.name,
        "file": str(path),
        "line": msg.line_number,
        "message": msg.message,
    }
    if msg.line_number is None:
        fields.pop("line")
    return json.dumps(fields)


def report(results: dict[Path, list[LogMessage]], fail_on: LogLevel, output_format: OutputFormat) -> int:
    """Print the messages, most severe first, and a summary. Returns the exit code: 1 if any is at least ``fail_on``."""
    formatter = _json if output_format is OutputFormat.JSON else _text
    flat = [(path, msg) for path, msgs in results.items() for msg in msgs]
    for path, msg in sorted(flat, key=lambda item: -item[1].loglevel):
        print(formatter(path, msg))

    if not flat:
        print("No issues found.")
        return 0

    counts = Counter(msg.loglevel for _, msg in flat)
    failed = any(level >= fail_on for level in counts)
    parts = [f"{counts[level]} {level}(s)" for level in sorted(counts, reverse=True)]
    print(f"{'Fail' if failed else 'Success'}: We found {', '.join(parts)}.")
    return 1 if failed else 0

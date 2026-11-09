"""Lint IDD files: report everything IddFile.validate finds, the file itself isn't changed."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from enum import Enum
from pathlib import Path

from energyplus_toolkit.input.idd.idd_field import IddFieldParseError
from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.log_message import LogLevel, LogMessage, use_color


class OutputFormat(Enum):
    TEXT = "text"
    JSON = "json"
    GITHUB_ACTIONS = "gha"


def lint_file(path: Path) -> list[LogMessage]:
    """The messages for this file. One that can't be parsed gets a single error."""
    try:
        messages = IddFile.load(path).validate()
    except (ValueError, IddFieldParseError) as exc:
        messages = [LogMessage(tool="idd-parse", loglevel=LogLevel.ERROR, message=str(exc))]
    return [replace(msg, filepath=path) for msg in messages]


def report(messages: list[LogMessage], fail_on: LogLevel, output_format: OutputFormat, verbose: bool = False) -> int:
    """Print the messages, most severe first, and a summary. Returns the exit code: 1 if any is at least ``fail_on``.

    Like EnergyPlus' base_hook.py, INFO is only printed if ``verbose`` (or if it fails), but always counted.
    """
    min_printed = LogLevel.INFO if verbose or fail_on == LogLevel.INFO else LogLevel.WARNING
    color = use_color()
    for msg in sorted(messages, key=lambda msg: -msg.loglevel):
        if msg.loglevel < min_printed:
            continue
        if output_format == OutputFormat.TEXT:
            print(msg.format(color=color))
        elif output_format == OutputFormat.JSON:
            print(msg.to_json())
        elif output_format == OutputFormat.GITHUB_ACTIONS:
            print(msg.to_github_annotation())

    if not messages:
        print("No issues found.")
        return 0

    counts = Counter(msg.loglevel for msg in messages)
    failed = any(level >= fail_on for level in counts)
    parts = [f"{counts[level]} {level}(s)" for level in sorted(counts, reverse=True)]
    print(f"{'Fail' if failed else 'Success'}: We found {', '.join(parts)}.")
    return 1 if failed else 0

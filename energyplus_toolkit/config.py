"""The [tool.energyplus-toolkit] table of pyproject.toml, like black's [tool.black]: defaults for the command line.

Its keys are the long option names, eg ``idd``, ``leading``, ``tag-column``, ``fail-on``. Each applies to the commands
that have that option, and the command line wins. A relative path is relative to the pyproject.toml.

    [tool.energyplus-toolkit]
    idd = "idd/Energy+.idd.in"
    fail-on = "warning"
"""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path
from typing import Any

TABLE = "energyplus-toolkit"

# What a single run does, not how the project is set up
NOT_CONFIGURABLE = frozenset({"check", "diff", "output", "config"})


class ConfigError(ValueError):
    pass


def regex(value: str) -> re.Pattern[str]:
    """The argparse type of --exclude, like black's validate_regex: an error rather than a traceback."""
    try:
        return re.compile(value)
    except re.error as exc:
        raise argparse.ArgumentTypeError(f"not a valid regular expression: {exc}") from None


def find_pyproject(start: Path) -> Path | None:
    """The closest pyproject.toml from ``start`` up, without leaving its repository (a folder with .git)."""
    for folder in [start, *start.parents]:
        if (path := folder / "pyproject.toml").is_file():
            return path
        if (folder / ".git").exists():
            return None
    return None


def load(path: Path) -> dict[str, Any]:
    """The [tool.energyplus-toolkit] table of ``path``, empty if it has none."""
    try:
        with open(path, "rb") as f:
            data = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from None
    table = data.get("tool", {}).get(TABLE, {})
    if not isinstance(table, dict):
        raise ConfigError(f"{path}: [tool.{TABLE}] must be a table")
    return table


def _leaf_parsers(parser: argparse.ArgumentParser) -> list[argparse.ArgumentParser]:
    """The parsers of the actual commands (format idf, lint idd...), which have the options."""
    subparsers = [action for action in parser._actions if isinstance(action, argparse._SubParsersAction)]
    if not subparsers:
        return [parser]
    return [leaf for action in subparsers for sub in action.choices.values() for leaf in _leaf_parsers(sub)]


def _option(parser: argparse.ArgumentParser, key: str) -> argparse.Action | None:
    return next((action for action in parser._actions if f"--{key}" in action.option_strings), None)


def _convert(action: argparse.Action, key: str, value: Any, base_dir: Path) -> Any:
    """``value`` as argparse would have turned it into from the command line."""
    if isinstance(action, argparse._StoreTrueAction):
        if not isinstance(value, bool):
            raise ConfigError(f"'{key}' must be true or false, got {value!r}")
        return value
    if action.type is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"'{key}' must be an integer, got {value!r}")
        return value
    if not isinstance(value, str):
        raise ConfigError(f"'{key}' must be a string, got {value!r}")
    if action.type is Path:
        return base_dir / value  # unchanged if absolute
    try:
        converted = action.type(value) if callable(action.type) else value
    except argparse.ArgumentTypeError as exc:
        raise ConfigError(f"'{key}': {exc}") from None
    if action.choices is not None and converted not in action.choices:
        raise ConfigError(f"'{key}' must be one of {', '.join(map(str, action.choices))}, got {value!r}")
    return converted


def apply(parser: argparse.ArgumentParser, table: dict[str, Any], path: Path) -> None:
    """Use ``table`` (from ``path``) as the defaults of the commands that have each option."""
    leaves = _leaf_parsers(parser)
    for key, value in table.items():
        options = [(leaf, action) for leaf in leaves if (action := _option(leaf, key)) is not None]
        if key in NOT_CONFIGURABLE or not options:
            raise ConfigError(f"{path}: unknown key '{key}' in [tool.{TABLE}]")
        for leaf, action in options:
            try:
                default = _convert(action, key, value, base_dir=path.parent)
            except (ConfigError, ValueError) as exc:
                raise ConfigError(f"{path}: {exc}") from None
            leaf.set_defaults(**{action.dest: default})
            # Given by the config, it no longer has to be on the command line
            action.required = False

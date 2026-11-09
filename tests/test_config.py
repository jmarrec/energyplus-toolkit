"""Tests for the [tool.energyplus-toolkit] table of pyproject.toml."""

import os
import shutil
from pathlib import Path

import pytest

from energyplus_toolkit.cli import main
from energyplus_toolkit.config import find_pyproject

RESOURCES = Path(__file__).parent / "resources"
IDD = RESOURCES / "V26-1-0-Energy+.idd"
IDF = RESOURCES / "1ZoneUncontrolled-V26-1-0.idf"

WARNING_IDD = "!IDD_Version 26.1.0\n\nSome:Object,\n  A1 ; \\field Name\n       \\required-field\n       \\default X\n"


@pytest.fixture
def project(tmp_path, monkeypatch) -> Path:
    """A repository with an IDF, an IDD with a lint warning, run from its root."""
    (tmp_path / ".git").mkdir()
    shutil.copy(IDF, tmp_path / "in.idf")
    (tmp_path / "warning.idd").write_text(WARNING_IDD)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _pyproject(folder: Path, table: str) -> Path:
    path = folder / "pyproject.toml"
    path.write_text(f"[tool.black]\nline-length = 120\n\n[tool.energyplus-toolkit]\n{table}\n")
    return path


def test_find_pyproject_goes_up(project):
    path = _pyproject(project, "")
    (project / "sub" / "deeper").mkdir(parents=True)
    assert find_pyproject(project / "sub" / "deeper") == path


def test_find_pyproject_stays_in_the_repository(project):
    """One above the repository isn't this project's."""
    _pyproject(project.parent, "")
    assert find_pyproject(project) is None


def test_idd_relative_to_the_pyproject(project, capsys):
    # Not --idd, which format idf requires, and run from a subfolder: relative to the pyproject.toml, not to it
    _pyproject(project, f'idd = "{os.path.relpath(IDD, project)}"')
    (project / "sub").mkdir()
    os.chdir(project / "sub")
    assert main(["format", "idf", "-o", "-", str(project / "in.idf")]) == 0
    assert capsys.readouterr().out.startswith("!-Generator IDFEditor")


def test_command_line_wins(project, capsys):
    _pyproject(project, f'idd = "{IDD}"\nleading = 4')
    assert main(["format", "idf", "-o", "-", "in.idf"]) == 0
    assert "\n    Version,26.1;\n" in capsys.readouterr().out
    assert main(["format", "idf", "--leading", "0", "-o", "-", "in.idf"]) == 0
    assert "\nVersion,26.1;\n" in capsys.readouterr().out


def test_lint_fail_on(project):
    assert main(["lint", "idd", "warning.idd"]) == 0
    _pyproject(project, 'fail-on = "warning"')
    assert main(["lint", "idd", "warning.idd"]) == 1


def test_option_of_another_command_is_ignored(project):
    """fail-on is for lint: format idd doesn't have it, and it's fine."""
    _pyproject(project, 'fail-on = "warning"\ntag-column = 9')
    assert main(["format", "idd", "-q", "warning.idd"]) == 0
    assert "\n         \\required-field\n" in (project / "warning.idd").read_text()


def test_explicit_config(project, tmp_path_factory):
    other = _pyproject(tmp_path_factory.mktemp("elsewhere"), 'fail-on = "warning"')
    assert main(["lint", "idd", "--config", str(other), "warning.idd"]) == 1


def test_no_table_is_no_config(project):
    (project / "pyproject.toml").write_text("[tool.black]\nline-length = 120\n")
    assert main(["lint", "idd", "warning.idd"]) == 0


@pytest.mark.parametrize(
    "table, message",
    [
        ("fail_on = 'warning'", "unknown key 'fail_on'"),
        ("check = true", "unknown key 'check'"),
        ("leading = 'two'", "'leading' must be an integer, got 'two'"),
        ("quiet = 1", "'quiet' must be true or false, got 1"),
        ("fail-on = 'loud'", "'fail-on' must be one of INFO, WARNING, ERROR, got 'loud'"),
        ("[tool.energyplus-toolkit", "pyproject.toml: "),
    ],
)
def test_bad_config_is_an_error(project, capsys, table, message):
    _pyproject(project, table)
    with pytest.raises(SystemExit) as exc:
        main(["lint", "idd", "warning.idd"])
    assert exc.value.code == 2
    assert message in capsys.readouterr().err


def test_explicit_config_not_found(project, capsys):
    with pytest.raises(SystemExit):
        main(["lint", "idd", "--config", "nope.toml", "warning.idd"])
    assert "--config: file not found: nope.toml" in capsys.readouterr().err

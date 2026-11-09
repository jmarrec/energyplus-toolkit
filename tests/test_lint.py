"""Tests for IDD validation and the lint CLI."""

import json
import re
from pathlib import Path

import pytest

from energyplus_toolkit.cli import main
from energyplus_toolkit.input.idd.idd_field import IddField
from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.idd.idd_object import IddObject
from energyplus_toolkit.input.log_message import LogLevel, LogMessage

RESOURCES = Path(__file__).parent / "resources"
IDD = RESOURCES / "V26-1-0-Energy+.idd"


def _object(*lines: str) -> IddObject:
    return IddObject.load(group="Test", object_lines=["Some:Object,", *lines])


def _idd(*lines: str) -> str:
    return "\n".join(["!IDD_Version 26.1.0", "", "Some:Object,", *lines, ""])


@pytest.mark.parametrize(
    "level, gha, icon",
    [(LogLevel.INFO, "notice", "ℹ️ "), (LogLevel.WARNING, "warning", "⚠️ "), (LogLevel.ERROR, "error", "❌")],
)
def test_log_level_to_gha_and_icon(level, gha, icon):
    assert level.to_gha() == gha
    assert level.to_icon() == icon


def test_validate_clean_object():
    assert _object("  A1 , \\field One", "  N1 , \\field Two", "  A2 ; \\field Three").validate() == []


def test_validate_gap_in_field_ids_is_one_message():
    """The count resumes from the gap: what comes after A3 isn't reported."""
    obj = _object("  A1 , \\field One", "  A3 , \\field Three", "  A4 , \\field Four", "  N1 ; \\field Five")
    assert obj.validate() == [
        LogMessage(
            tool="idd-field-ids",
            loglevel=LogLevel.ERROR,
            message="In 'Some:Object', field 'Three': expected field ID A2, got A3",
        )
    ]


def test_validate_duplicate_field_id():
    messages = _object("  N1 , \\field One", "  N1 ; \\field Two").validate()
    assert [m.message for m in messages] == ["In 'Some:Object', field 'Two': expected field ID N2, got N1"]


def test_validate_field_ids_must_start_at_one():
    messages = _object("  A2 ; \\field One").validate()
    assert [m.message for m in messages] == ["In 'Some:Object', field 'One': expected field ID A1, got A2"]


def test_validate_all_gaps_are_reported():
    obj = _object("  A1 , \\field One", "  A3 , \\field Two", "  N2 , \\field Three", "  A5 ; \\field Four")
    assert [m.message.rsplit(": ")[-1] for m in obj.validate()] == [
        "expected field ID A2, got A3",
        "expected field ID N1, got N2",
        "expected field ID A4, got A5",
    ]


def test_validate_first_extensible_group_ids():
    obj = _object("  \\extensible:1", "  A1 , \\field Name", "  N2 ; \\field V 1", "  \\begin-extensible")
    assert [m.tool for m in obj.validate()] == ["idd-field-ids"]


def test_validate_extensible_without_begin_extensible():
    """ComfortViewFactorAngles, V9-6-0 to V25-1-0."""
    messages = _object("  \\extensible:1", "  A1 ; \\field Name").validate()
    assert [(m.tool, m.message) for m in messages] == [
        ("idd-extensible", "In 'Some:Object': Object is extensible but has no extensible fields")
    ]


def test_validate_extensible_group_too_short():
    obj = _object("  \\extensible:2", "  N1 ; \\field V 1", "  \\begin-extensible")
    assert [m.message for m in obj.validate()] == ["In 'Some:Object': \\extensible:2 but 1 extensible fields"]


@pytest.mark.parametrize("default", ["0", "Yes", "autosize"])
def test_validate_required_with_default(default):
    field = IddField.load(
        objectName="Some:Object",
        field_lines=["  A1 , \\field Name", "       \\required-field", f"       \\default {default}"],
    )
    assert field.validate() == [
        LogMessage(
            tool="idd-required-default",
            loglevel=LogLevel.WARNING,
            message="In 'Some:Object', field 'Name': Field has \\default, remove \\required-field",
        )
    ]


@pytest.mark.parametrize("extra", ["\\required-field", "\\default 0"])
def test_validate_required_or_default_alone_is_fine(extra):
    field = IddField.load(objectName="Some:Object", field_lines=["  A1 , \\field Name", f"       {extra}"])
    assert field.validate() == []


def test_validate_type_incompatible_with_field_id():
    """Chiller:Electric:ASHRAE205, before its flow rates became N fields."""
    field = IddField.load(objectName="Some:Object", field_lines=["  A1 , \\field Name", "       \\type real"])
    assert [(m.tool, m.loglevel) for m in field.validate()] == [("idd-field-type", LogLevel.ERROR)]


def test_validate_numeric_choice_is_fine():
    """WindowMaterial:Screen: numeric keys."""
    field_lines = ["  N1 , \\field Name", "       \\type choice", "       \\key 0"]
    assert IddField.load(objectName="Some:Object", field_lines=field_lines).validate() == []


def test_validate_real_idd():
    """These gaps are in V26-1-0, they were fixed afterwards."""
    messages = IddFile.load(IDD).validate()
    ids = [m.message for m in messages if m.tool == "idd-field-ids"]
    assert len(ids) == 4, ids  # HeatPump:AirToWater has two gaps
    assert any("PipingSystem:Underground:PipeSegment" in m for m in ids)
    assert any("Curve:QuadLinear" in m for m in ids)
    assert any("HeatPump:AirToWater" in m for m in ids)


@pytest.fixture
def clean_idd(tmp_path: Path) -> Path:
    path = tmp_path / "clean.idd"
    path.write_text(_idd("  A1 ; \\field Name"))
    return path


@pytest.fixture
def warning_idd(tmp_path: Path) -> Path:
    path = tmp_path / "warning.idd"
    path.write_text(_idd("  A1 ; \\field Name", "       \\required-field", "       \\default X"))
    return path


@pytest.fixture
def error_idd(tmp_path: Path) -> Path:
    path = tmp_path / "error.idd"
    path.write_text(_idd("  A2 ; \\field Name"))
    return path


def test_cli_lint_clean(clean_idd, capsys):
    assert main(["lint", "idd", str(clean_idd)]) == 0
    assert capsys.readouterr().out == "No issues found.\n"


def test_cli_lint_does_not_change_the_file(error_idd):
    before = error_idd.read_text()
    main(["lint", "idd", str(error_idd)])
    assert error_idd.read_text() == before


def _lint_json(capsys, *args: str) -> tuple[int, list[dict], str]:
    """Run lint idd with --output-format json: the exit code, the messages, and the summary line."""
    code = main(["lint", "idd", "--output-format", "json", *args])
    *messages, summary = capsys.readouterr().out.splitlines()
    return code, [json.loads(line) for line in messages], summary


def test_cli_lint_error_fails(error_idd, capsys):
    code, messages, summary = _lint_json(capsys, str(error_idd))
    assert code == 1
    assert [(m["loglevel"], m["tool"], m["file"]) for m in messages] == [("Error", "idd-field-ids", str(error_idd))]
    assert summary == "Fail: We found 1 Error(s)."


def test_cli_lint_warning_passes_by_default(warning_idd, capsys):
    code, messages, summary = _lint_json(capsys, str(warning_idd))
    assert code == 0
    assert [(m["loglevel"], m["tool"]) for m in messages] == [("Warning", "idd-required-default")]
    assert summary == "Success: We found 1 Warning(s)."


def test_cli_lint_fail_on_warning(warning_idd):
    assert main(["lint", "idd", "--fail-on", "warning", str(warning_idd)]) == 1


def test_cli_lint_folder_most_severe_first(tmp_path, warning_idd, error_idd, capsys):
    code, messages, summary = _lint_json(capsys, str(tmp_path))
    assert code == 1
    assert [m["loglevel"] for m in messages] == ["Error", "Warning"]
    assert summary == "Fail: We found 1 Error(s), 1 Warning(s)."


def test_cli_lint_json(error_idd, capsys):
    assert main(["lint", "idd", "--output-format", "json", str(error_idd)]) == 1
    assert json.loads(capsys.readouterr().out.splitlines()[0]) == {
        "tool": "idd-field-ids",
        "loglevel": "Error",
        "filename": "error.idd",
        "file": str(error_idd),
        "message": "In 'Some:Object', field 'Name': expected field ID A1, got A2",
    }


def test_cli_lint_github_actions(error_idd, capsys, monkeypatch):
    # A relative path, like in a workflow run from the repo root (an absolute one has C: on Windows, which gets escaped)
    monkeypatch.chdir(error_idd.parent)
    assert main(["lint", "idd", "--output-format", "gha", error_idd.name]) == 1
    first = capsys.readouterr().out.splitlines()[0]
    assert first.startswith(
        f"::error file={error_idd.name},line=1,title=idd-field-ids::In 'Some:Object', field 'Name': "
    )


def test_cli_lint_file_that_does_not_parse(tmp_path, capsys):
    path = tmp_path / "broken.idd"
    path.write_text("not an idd\n")
    code, messages, _ = _lint_json(capsys, str(path))
    assert code == 1
    assert [(m["loglevel"], m["tool"]) for m in messages] == [("Error", "idd-parse")]


def test_log_message_without_filepath():
    msg = LogMessage(tool="idd-field-ids", loglevel=LogLevel.ERROR, message="Gap")
    assert msg.to_dict() == {"tool": "idd-field-ids", "loglevel": "Error", "message": "Gap"}
    assert msg.to_github_annotation() == "::error title=idd-field-ids::Gap"


def test_log_message_github_annotation():
    msg = LogMessage(
        tool="idd-field-ids",
        loglevel=LogLevel.WARNING,
        message="Field 'A': 50% off\nnext",
        line="A1;",
        filepath=Path("a.idd"),
    )
    # No line number: GitHub still needs one to place it in the file. The ':' in the message is left alone
    assert (
        msg.to_github_annotation()
        == "::warning file=a.idd,line=1,title=idd-field-ids::Field 'A': 50%25 off%0Anext%0AA1;"
    )


def test_log_message_github_annotation_escapes_properties():
    msg = LogMessage(tool="idd-field-ids", loglevel=LogLevel.ERROR, message="Gap", filepath=Path("C:/a,b.idd"))
    assert msg.to_github_annotation() == "::error file=C%3A/a%2Cb.idd,line=1,title=idd-field-ids::Gap"


def test_log_message_color_only_adds_ansi_codes():
    """Not the layout, which is free to change: only that color doesn't change the text."""
    msg = LogMessage(
        tool="idd-field-ids", loglevel=LogLevel.ERROR, message="Gap", line_number=3, filepath=Path("a.idd")
    )
    colored = msg.format(color=True)
    assert "\033[" in colored
    assert re.sub(r"\033\[[0-9;]*m", "", colored) == str(msg) == msg.format()


@pytest.fixture
def info_idd(tmp_path) -> Path:
    """An \\ip-units that is already the default: an info."""
    header = (
        "!IDD_Version 26.1.0\n"
        "! Default IP conversions (no \\ip-units necessary)\n"
        "!      m                      =>   ft                  3.28083989501312\n"
        "! **************************************************************************\n"
    )
    path = tmp_path / "info.idd"
    path.write_text(f"{header}\nSome:Object,\n  N1 ; \\field Value\n       \\units m\n       \\ip-units ft\n")
    return path


@pytest.mark.parametrize(
    "args, printed",
    [([], []), (["--verbose"], ["Info"]), (["--fail-on", "info"], ["Info"])],
)
def test_cli_lint_info_is_only_printed_if_verbose(info_idd, capsys, args, printed):
    code, messages, summary = _lint_json(capsys, *args, str(info_idd))
    assert [m["loglevel"] for m in messages] == printed
    # Always counted
    assert summary.endswith("We found 1 Info(s).")
    assert code == (1 if "--fail-on" in args else 0)

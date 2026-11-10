"""Tests for the black-style CLI: files and folders, in place, --check, --diff, -o, --exclude, workers."""

import shutil
from pathlib import Path

import pytest

from energyplus_toolkit.cli import main
from tests.idd.test_idd_file import idd_text

RESOURCES = Path(__file__).parent / "resources"
IDD = str(RESOURCES / "V26-1-0-Energy+.idd")
UNIT_TEST = RESOURCES / "cpp" / "Example.unit.cc"
UNIT_TEST_EXPECTED = (RESOURCES / "cpp" / "Example.unit.expected.cc").read_text()

ZONE_IDF = "Version,26.1;\n\nZone,Z1,0,0,0,0;\n"


@pytest.fixture
def unit_tests(tmp_path: Path) -> Path:
    """A folder with two unit test files, one in a subfolder, and a file that isn't a unit test."""
    shutil.copy(UNIT_TEST, tmp_path / "A.unit.cc")
    (tmp_path / "sub").mkdir()
    shutil.copy(UNIT_TEST, tmp_path / "sub" / "B.unit.cc")
    shutil.copy(UNIT_TEST, tmp_path / "helper.cc")
    return tmp_path


def test_folder_reformatted_in_place(unit_tests, capsys):
    assert main(["format", "unit-test", "--idd", IDD, str(unit_tests)]) == 0
    assert (unit_tests / "A.unit.cc").read_text() == UNIT_TEST_EXPECTED
    assert (unit_tests / "sub" / "B.unit.cc").read_text() == UNIT_TEST_EXPECTED
    assert (unit_tests / "helper.cc").read_text() == UNIT_TEST.read_text()  # not a *.unit.cc
    err = capsys.readouterr().err
    assert "reformatted" in err and "2 files reformatted." in err

    # Second run: nothing to do
    assert main(["format", "unit-test", "--idd", IDD, "--check", str(unit_tests)]) == 0
    assert "2 files would be left unchanged." in capsys.readouterr().err


def test_check_does_not_write(unit_tests, capsys):
    assert main(["format", "unit-test", "--idd", IDD, "--check", str(unit_tests)]) == 1
    assert (unit_tests / "A.unit.cc").read_text() == UNIT_TEST.read_text()
    err = capsys.readouterr().err
    assert f"would reformat {unit_tests / 'A.unit.cc'}" in err
    assert "2 files would be reformatted." in err


def test_diff_does_not_write(unit_tests, capsys):
    assert main(["format", "unit-test", "--idd", IDD, "--diff", str(unit_tests / "A.unit.cc")]) == 0
    assert (unit_tests / "A.unit.cc").read_text() == UNIT_TEST.read_text()
    out = capsys.readouterr().out
    assert out.startswith(f"--- {unit_tests / 'A.unit.cc'}\t(original)")
    assert '+        "Zone,",' in out


def test_exclude_skips_found_files_but_not_explicit_ones(unit_tests):
    assert main(["format", "unit-test", "--idd", IDD, "--exclude", "sub/", str(unit_tests)]) == 0
    assert (unit_tests / "A.unit.cc").read_text() == UNIT_TEST_EXPECTED
    assert (unit_tests / "sub" / "B.unit.cc").read_text() == UNIT_TEST.read_text()

    explicit = str(unit_tests / "sub" / "B.unit.cc")
    assert main(["format", "unit-test", "--idd", IDD, "--exclude", "sub/", explicit]) == 0
    assert (unit_tests / "sub" / "B.unit.cc").read_text() == UNIT_TEST_EXPECTED


def test_workers_give_the_same_result(tmp_path):
    for workers, folder in [("1", tmp_path / "serial"), ("3", tmp_path / "parallel")]:
        folder.mkdir()
        for i in range(4):
            shutil.copy(UNIT_TEST, folder / f"T{i}.unit.cc")
        assert main(["format", "unit-test", "--idd", IDD, "-j", workers, "-q", str(folder)]) == 0
    for i in range(4):
        assert (tmp_path / "parallel" / f"T{i}.unit.cc").read_text() == UNIT_TEST_EXPECTED
        assert (tmp_path / "serial" / f"T{i}.unit.cc").read_text() == UNIT_TEST_EXPECTED


def test_output_to_stdout(unit_tests, capsys):
    assert main(["format", "unit-test", "--idd", IDD, "-o", "-", str(unit_tests / "A.unit.cc")]) == 0
    assert capsys.readouterr().out == UNIT_TEST_EXPECTED
    assert (unit_tests / "A.unit.cc").read_text() == UNIT_TEST.read_text()


def test_output_needs_a_single_file(unit_tests):
    with pytest.raises(SystemExit) as exc:
        main(["format", "unit-test", "--idd", IDD, "-o", "-", str(unit_tests)])
    assert exc.value.code == 2


def test_error_in_one_file_does_not_stop_the_others(unit_tests, capsys):
    (unit_tests / "Bad.unit.cc").write_bytes(b"\xff\xfe not utf-8 \n")
    assert main(["format", "unit-test", "--idd", IDD, str(unit_tests)]) == 123
    assert (unit_tests / "A.unit.cc").read_text() == UNIT_TEST_EXPECTED
    err = capsys.readouterr().err
    assert f"error: cannot reformat {unit_tests / 'Bad.unit.cc'}" in err
    assert "2 files reformatted, 1 file failed to reformat." in err


def test_warnings_show_the_file_and_quiet_hides_them(tmp_path, capsys):
    path = tmp_path / "W.unit.cc"
    path.write_text("""\
    std::string const idf_objects = delimited_string({
        "  Zone,",
        some_variable,
        "    Z1;",
    });
""")
    assert main(["format", "unit-test", "--idd", IDD, str(path)]) == 0
    assert f"{path}: warning: " in capsys.readouterr().err
    assert main(["format", "unit-test", "--idd", IDD, "-q", str(path)]) == 0
    assert capsys.readouterr().err == "1 file left unchanged.\n"


def test_reformat_idf_keep_integer_reals(tmp_path):
    path = tmp_path / "in.idf"
    path.write_text(ZONE_IDF)
    assert main(["format", "idf", "--idd", IDD, "-q", "--keep-integer-reals", str(path)]) == 0
    assert "  0,                       !- Direction of Relative North {deg}" in path.read_text()

    path.write_text(ZONE_IDF)
    assert main(["format", "idf", "--idd", IDD, "-q", str(path)]) == 0
    assert "  0.0,                     !- Direction of Relative North {deg}" in path.read_text()


def test_crlf_line_endings_are_kept(tmp_path):
    path = tmp_path / "in.idf"
    path.write_bytes(ZONE_IDF.replace("\n", "\r\n").encode())
    assert main(["format", "idf", "--idd", IDD, "-q", str(path)]) == 0
    data = path.read_bytes()
    assert b"\r\n" in data
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_reformat_idd(tmp_path):
    path = tmp_path / "mini.idd"
    path.write_text(idd_text())
    assert main(["format", "idd", "-q", str(tmp_path)]) == 0
    assert main(["format", "idd", "--check", str(path)]) == 0  # stable


def test_missing_path_is_an_error(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main(["format", "idf", "--idd", IDD, str(tmp_path / "nope.idf")])
    assert exc.value.code == 2


def test_reformat_idf_ignores_imf(tmp_path, capsys):
    """IMF files (EP-Macro) are skipped, in folders and when given explicitly (as pre-commit does)."""
    (tmp_path / "a.idf").write_text(ZONE_IDF)
    imf = tmp_path / "b.imf"
    imf.write_text("##include something.imf\n")
    assert main(["format", "idf", "--idd", IDD, "--check", str(tmp_path), str(imf)]) == 1
    assert capsys.readouterr().err.splitlines()[-1] == "1 file would be reformatted."


def test_reformat_idf_leaves_parametric_files_unchanged(tmp_path, capsys):
    """1ZoneParameterAspect.idf: "=$height" is for the parametric preprocessor, the file isn't a valid IDF yet."""
    path = tmp_path / "parametric.idf"
    text = "Version,26.1;\n  Parametric:SetValueForRun,\n    $height,3;\nZone,Z1,0,0,0,0,1,1,=$height;\n"
    path.write_text(text)
    assert main(["format", "idf", "--idd", IDD, str(path)]) == 0
    assert path.read_text() == text
    err = capsys.readouterr().err
    assert "Parametric objects" in err
    assert err.splitlines()[-1] == "1 file left unchanged."


def test_reformat_idf_parametric_in_a_comment_is_reformatted(tmp_path):
    path = tmp_path / "in.idf"
    path.write_text("! Parametric:SetValueForRun is not used here\nVersion,26.1;\nZone,Z1; ! Parametric: nope\n")
    assert main(["format", "idf", "--idd", IDD, "-q", str(path)]) == 0
    assert "Zone,\n  Z1;                      ! Parametric: nope\n" in path.read_text()  # reformatted


@pytest.mark.parametrize(
    "text, warning",
    [
        # datasets/PrecipitationSchedulesUSA-fullset_Release.idf: a placeholder, not an IDF
        ('You need to obtain the "PreciptationSchedulesUSA-fullset.idf" from the helpdesk\n', "text outside"),
        ("Version,26.1;\nNot:An:Object,A;\nZone,Z1;\n", "expected 3 IDF object(s) but parsed 2"),
    ],
    ids=["text-outside-fields", "unknown-object"],
)
def test_reformat_idf_never_loses_content(tmp_path, capsys, text, warning):
    """When IdfFile would drop part of the file, it's left unchanged, with a warning."""
    path = tmp_path / "in.idf"
    path.write_text(text)
    assert main(["format", "idf", "--idd", IDD, str(path)]) == 0
    assert path.read_text() == text
    err = capsys.readouterr().err
    assert warning in err
    assert err.splitlines()[-1] == "1 file left unchanged."


SMALL_IDD = "!IDD_Version 26.1.0\n\nSome:Object,\n  A1 ; \\field Name\n       \\type alpha\n"


def test_reformat_idd_tag_column(tmp_path):
    path = tmp_path / "small.idd"
    path.write_text(SMALL_IDD)
    assert main(["format", "idd", "-q", "--tag-column", "9", str(path)]) == 0
    assert "  A1   ; \\field Name\n         \\type alpha\n" in path.read_text()
    assert main(["format", "idd", "--check", "--tag-column", "9", str(path)]) == 0  # stable
    assert main(["format", "idd", "--check", str(path)]) == 1  # not the default layout


def test_reformat_idd_tag_column_too_small(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["format", "idd", "--tag-column", "5", str(tmp_path)])
    assert "--tag-column must be at least 6, got 5" in capsys.readouterr().err


def test_reformat_idf_negative_leading(tmp_path, capsys):
    with pytest.raises(SystemExit):
        main(["format", "idf", "--idd", IDD, "--leading", "-1", str(tmp_path)])
    assert "--leading must be at least 0, got -1" in capsys.readouterr().err


def test_bad_exclude_regex_is_an_error(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["lint", "idd", "--exclude", "[", "."])
    assert exc.value.code == 2
    assert "argument --exclude: not a valid regular expression: unterminated character set" in capsys.readouterr().err

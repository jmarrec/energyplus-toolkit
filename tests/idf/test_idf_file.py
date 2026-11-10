"""Tests for IdfFile."""

from pathlib import Path

import pytest

from energyplus_toolkit.input.format_options import FormatOptions
from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.idd.idd_object import IddObject
from energyplus_toolkit.input.idf.idf_file import IdfFile, split_objects_on_one_line
from energyplus_toolkit.input.idf.idf_object import IdfObject

RESOURCES = Path(__file__).parent.parent / "resources"


@pytest.fixture(scope="session")
def ep_idd() -> IddFile:
    return IddFile.load(RESOURCES / "V26-1-0-Energy+.idd")


# ---------------------------------------------------------------------------
# Small self-contained IDF text (no real IDD needed)
# ---------------------------------------------------------------------------

MINI_IDD_ZONE = """\
Zone,
       \\memo Thermal zone
  A1,  \\field Name
       \\type alpha
       \\reference Zones
  N1;  \\field Floor Area
       \\type real
       \\units m2
"""

MINI_IDD_SIMCTRL = """\
SimulationControl,
       \\unique-object
  A1,  \\field Do Zone Sizing Calculation
       \\type choice
       \\key Yes
       \\key No
       \\default No
  A2;  \\field Do System Sizing Calculation
       \\type choice
       \\key Yes
       \\key No
       \\default No
"""


def make_mini_idd(*idd_texts: str) -> IddFile:
    idd = IddFile()
    for text in idd_texts:
        obj = IddObject.load(group="TestGroup", object_lines=text.splitlines())
        idd.objects.append(obj)
    return idd


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_idf_file_empty():
    idd = make_mini_idd(MINI_IDD_ZONE)
    idf = IdfFile(idd_file=idd)
    assert idf.num_objects() == 0
    assert idf.header == ""
    assert idf.objects == []


def test_idf_file_repr():
    idd = make_mini_idd(MINI_IDD_ZONE)
    idf = IdfFile(idd_file=idd)
    assert "0 objects" in repr(idf)


# ---------------------------------------------------------------------------
# loads / parsing
# ---------------------------------------------------------------------------


def test_idf_file_loads_single_object():
    idd = make_mini_idd(MINI_IDD_ZONE)
    text = """
Zone,
  My Zone,
  100.0;
"""
    idf = IdfFile.loads(text, idd)
    assert idf.num_objects() == 1
    assert idf.objects[0].name == "My Zone"


def test_idf_file_loads_header_comment():
    idd = make_mini_idd(MINI_IDD_ZONE)
    text = """\
! EnergyPlus IDF file
! Generated automatically

Zone,
  TestZone,
  50.0;
"""
    idf = IdfFile.loads(text, idd)
    assert "EnergyPlus IDF file" in idf.header
    assert idf.num_objects() == 1


def test_idf_file_loads_multiple_objects():
    idd = make_mini_idd(MINI_IDD_ZONE, MINI_IDD_SIMCTRL)
    text = """\
Zone,
  Zone1,
  100.0;

Zone,
  Zone2,
  200.0;

SimulationControl,
  Yes,
  No;
"""
    idf = IdfFile.loads(text, idd)
    assert idf.num_objects() == 3


def test_idf_file_loads_unknown_type_skipped(caplog):
    idd = make_mini_idd(MINI_IDD_ZONE)
    text = """\
Zone,
  GoodZone,
  50.0;

UnknownObject,
  SomeField;
"""
    import logging

    with caplog.at_level(logging.WARNING, logger="IdfFile"):
        idf = IdfFile.loads(text, idd)
    assert idf.num_objects() == 1
    assert any("UnknownObject" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# get_objects_by_type / get_objects_by_name
# ---------------------------------------------------------------------------


def test_idf_file_get_objects_by_type():
    idd = make_mini_idd(MINI_IDD_ZONE, MINI_IDD_SIMCTRL)
    text = "Zone,\n  A,\n  1.0;\n\nZone,\n  B,\n  2.0;\n\nSimulationControl,\n  Yes,\n  No;\n"
    idf = IdfFile.loads(text, idd)

    zones = idf.get_objects_by_type("Zone")
    assert len(zones) == 2

    sc = idf.get_objects_by_type("SimulationControl")
    assert len(sc) == 1


def test_idf_file_get_objects_by_type_idd_object():
    idd = make_mini_idd(MINI_IDD_ZONE)
    text = "Zone,\n  A,\n  1.0;\n"
    idf = IdfFile.loads(text, idd)

    idd_obj = idd.getObject("Zone")
    assert idf.get_objects_by_type(idd_obj) == idf.get_objects_by_type("Zone")


def test_idf_file_get_objects_by_name():
    idd = make_mini_idd(MINI_IDD_ZONE)
    text = "Zone,\n  Alpha,\n  1.0;\n\nZone,\n  Beta,\n  2.0;\n"
    idf = IdfFile.loads(text, idd)

    assert len(idf.get_objects_by_name("Alpha")) == 1
    assert len(idf.get_objects_by_name("alpha")) == 1  # case-insensitive
    assert len(idf.get_objects_by_name("NoSuchName")) == 0


# ---------------------------------------------------------------------------
# add / remove
# ---------------------------------------------------------------------------


def test_idf_file_add_object():
    idd = make_mini_idd(MINI_IDD_ZONE)
    idf = IdfFile(idd_file=idd)
    obj = IdfObject(idd_object=idd.getObject("Zone"))
    obj.setName("NewZone")
    idf.add_object(obj)
    assert idf.num_objects() == 1
    assert idf.get_object(0) is obj


def test_idf_file_remove_object():
    idd = make_mini_idd(MINI_IDD_ZONE)
    idf = IdfFile.loads("Zone,\n  Z1,\n  1.0;\n\nZone,\n  Z2,\n  2.0;\n", idd)
    target = idf.get_objects_by_name("Z1")[0]
    removed = idf.remove_object(target)
    assert removed is True
    assert idf.num_objects() == 1
    assert idf.get_objects_by_name("Z1") == []


def test_idf_file_remove_object_not_found():
    idd = make_mini_idd(MINI_IDD_ZONE)
    idf = IdfFile(idd_file=idd)
    orphan = IdfObject(idd_object=idd.getObject("Zone"))
    assert idf.remove_object(orphan) is False


# ---------------------------------------------------------------------------
# Serialisation / save
# ---------------------------------------------------------------------------


def test_idf_file_str_roundtrip():
    idd = make_mini_idd(MINI_IDD_ZONE)
    text = "Zone,\n  MyZone,\n  99.0;\n"
    idf = IdfFile.loads(text, idd)
    serialised = str(idf)

    idf2 = IdfFile.loads(serialised, idd)
    assert idf2.num_objects() == 1
    assert idf2.objects[0].name == "MyZone"


def test_idf_file_save_and_load(tmp_path):
    idd = make_mini_idd(MINI_IDD_ZONE)
    idf = IdfFile.loads("Zone,\n  SavedZone,\n  10.0;\n", idd)

    out = tmp_path / "test.idf"
    assert idf.save(out) is True
    assert out.exists()

    idf2 = IdfFile.load(out, idd)
    assert idf2.num_objects() == 1
    assert idf2.objects[0].name == "SavedZone"


def test_idf_file_save_no_overwrite(tmp_path):
    idd = make_mini_idd(MINI_IDD_ZONE)
    idf = IdfFile(idd_file=idd)
    out = tmp_path / "existing.idf"
    out.write_text("existing content")
    assert idf.save(out, overwrite=False) is False
    assert out.read_text() == "existing content"


# ---------------------------------------------------------------------------
# Integration: real EnergyPlus IDD
# ---------------------------------------------------------------------------


def test_idf_file_loads_real_idf(ep_idd):
    """Parse a minimal but realistic IDF snippet using the real EnergyPlus IDD."""
    text = """\
! Minimal EnergyPlus IDF

Version,
  26.1;

SimulationControl,
  No,
  No,
  No,
  Yes,
  Yes;

Zone,
  Living Zone,
  0,
  0,
  0,
  0;
"""
    idf = IdfFile.loads(text, ep_idd)
    assert idf.num_objects() == 3
    assert idf.num_objects_of_type("Version") == 1
    assert idf.num_objects_of_type("SimulationControl") == 1
    zones = idf.get_objects_by_type("Zone")
    assert len(zones) == 1
    assert zones[0].name == "Living Zone"


# ---------------------------------------------------------------------------
# Serialisation tests
# ---------------------------------------------------------------------------


def test_idf_file_str_no_header():
    idf_text = """Zone,
  MyZone,
  99.0;
"""
    idf = IdfFile.loads(idf_text, make_mini_idd(MINI_IDD_ZONE))
    expected = "\n".join(
        [
            "Zone,",
            "  MyZone,                  !- Name",
            "  99.0;                    !- Floor Area {m2}",
            "",
        ]
    )
    assert str(idf) == expected


def test_idf_file_str_with_header():
    idf_text = """! My EnergyPlus IDF

Zone,
  MyZone,
  99.0;
"""
    idf = IdfFile.loads(idf_text, make_mini_idd(MINI_IDD_ZONE))
    expected = "\n".join(
        [
            "! My EnergyPlus IDF",
            "",
            "Zone,",
            "  MyZone,                  !- Name",
            "  99.0;                    !- Floor Area {m2}",
            "",
        ]
    )
    assert str(idf) == expected


def test_idf_file_str_multiple_objects():
    idf_text = """! File header

Zone,
  ZoneA,
  10.0;

Zone,
  ZoneB,
  20.0;
"""
    idf = IdfFile.loads(idf_text, make_mini_idd(MINI_IDD_ZONE))
    expected = "\n".join(
        [
            "! File header",
            "",
            "Zone,",
            "  ZoneA,                   !- Name",
            "  10.0;                    !- Floor Area {m2}",
            "",
            "Zone,",
            "  ZoneB,                   !- Name",
            "  20.0;                    !- Floor Area {m2}",
            "",
        ]
    )
    assert str(idf) == expected


def test_idf_file_str_attached_object_comment():
    idf_text = """! File header

Zone,
  ZoneA,
  10.0;

! This is Zone B
Zone,
  ZoneB,
  20.0;
"""
    idf = IdfFile.loads(idf_text, make_mini_idd(MINI_IDD_ZONE))
    expected = "\n".join(
        [
            "! File header",
            "",
            "Zone,",
            "  ZoneA,                   !- Name",
            "  10.0;                    !- Floor Area {m2}",
            "",
            "! This is Zone B",
            "Zone,",
            "  ZoneB,                   !- Name",
            "  20.0;                    !- Floor Area {m2}",
            "",
        ]
    )
    assert str(idf) == expected


def test_idf_file_str_detached_comment_no_header():
    """A standalone comment between two objects when there is no file header should
    remain between those objects in the output, not be promoted to the file header."""
    idf_text = """\
Zone,
  ZoneA,
  10.0;

! A detached comment

Zone,
  ZoneB,
  20.0;
"""
    idf = IdfFile.loads(idf_text, make_mini_idd(MINI_IDD_ZONE))
    expected = "\n".join(
        [
            "Zone,",
            "  ZoneA,                   !- Name",
            "  10.0;                    !- Floor Area {m2}",
            "",
            "! A detached comment",
            "",
            "Zone,",
            "  ZoneB,                   !- Name",
            "  20.0;                    !- Floor Area {m2}",
            "",
        ]
    )
    assert str(idf) == expected


def test_idf_file_str_all_comment_types():
    """A standalone comment between two objects when there is no file header should
    remain between those objects in the output, not be promoted to the file header."""
    idf_text = """\
! This is a header
! with multiple lines

  ! This is an object comment
  Zone,
    ZoneA, ! This is a field comment for the Name field
    10.0;

  ! A detached comment

  ! Regular object comment
  Zone,
    ! A comment placed before the fields is understood as an object comment
    ZoneB, ! This is a field comment for the Name field
    20.0;

Zone, ! This is also understood as an object comment
  ZoneC,
  30.0;

  ! Another detached comment
"""
    idf = IdfFile.loads(idf_text, make_mini_idd(MINI_IDD_ZONE))
    expected = "\n".join(
        [
            "! This is a header",
            "! with multiple lines",
            "",
            "! This is an object comment",
            "Zone,",
            "  ZoneA,                   ! This is a field comment for the Name field",
            "  10.0;                    !- Floor Area {m2}",
            "",
            "! A detached comment",
            "",
            "! Regular object comment",
            "! A comment placed before the fields is understood as an object comment",
            "Zone,",
            "  ZoneB,                   ! This is a field comment for the Name field",
            "  20.0;                    !- Floor Area {m2}",
            "",
            "! This is also understood as an object comment",
            "Zone,",
            "  ZoneC,                   !- Name",
            "  30.0;                    !- Floor Area {m2}",
            "",
            "! Another detached comment",
            "",
        ]
    )
    assert str(idf) == expected


# ---------------------------------------------------------------------------
# Integration: real IDF serialisation with leading 2
# ---------------------------------------------------------------------------


def test_idf_file_str_1zone_uncontrolled_leading2(ep_idd):
    """Load the 1ZoneUncontrolled IDF, serialise with leading 2, and verify
    structural and spot-check properties of the output."""
    idf_path = RESOURCES / "1ZoneUncontrolled-V26-1-0.idf"
    idf = IdfFile.load(idf_path, ep_idd)

    result = idf.to_string(FormatOptions(leading=2))

    lines = result.splitlines()

    # Header is preserved unchanged
    assert lines[0] == "!-Generator IDFEditor 1.34"

    # Every object line (not comment, not blank) starts with exactly 2 spaces
    object_type_lines = [
        line for line in lines if line and not line.startswith("!") and not line.startswith("  ")  # exclude field lines
    ]
    assert object_type_lines == [], "All non-comment non-blank lines must be indented by 2"

    # Field lines start with 4 spaces (leading 2 + indent 2)
    field_lines = [line for line in lines if line.startswith("    ") and ("!-" in line)]
    assert len(field_lines) > 0, "Expected field lines with 4-space indent"
    for line in field_lines:
        assert line.startswith("    "), f"Field line not indented by 4: {line!r}"

    # Spot-check: Version object — singleLine format, all on one line
    assert any(ln == "  Version,26.1;" for ln in lines), "Version must be on a single line"

    # Spot-check: Building object name field
    building_start = next(i for i, ln in enumerate(lines) if ln == "  Building,")
    assert lines[building_start + 1] == "    Simple One Zone (Wireframe DXF),  !- Name"

    # All 88 objects are present
    assert idf.num_objects() == 88


@pytest.mark.parametrize(
    "one_line, separate_lines",
    [
        ("Timestep,4;Zone,Z1;\n", "Timestep,4;\nZone,Z1;\n"),
        # The next object continues on the following lines
        ("Timestep,4;Zone,\n  Z1;\n", "Timestep,4;\nZone,\n  Z1;\n"),
        # A comment after the last ';' stays with the last object
        ("Timestep,4;Zone,Z1;  ! My zone\n", "Timestep,4;\nZone,Z1;  ! My zone\n"),
        # A comment right after a ';' is on that object's line: it stays with it, not with the next object (C++: a
        # missing comma between "Timestep,4;" and "! something",)
        ("Timestep,4;! something\nZone,Z1;\n", "Timestep,4;  ! something\nZone,Z1;\n"),
    ],
    ids=["two-objects", "next-object-continues", "comment", "comment-after-semicolon"],
)
def test_idf_file_several_objects_on_one_line(ep_idd, one_line, separate_lines):
    """Valid IDF: a ';' ends an object, the next one can start on the same line. That's what EnergyPlus gets from two
    C++ strings concatenated because of a missing comma (ChillerReformulatedEIR.unit.cc: "...10.0;" "Curve:...")."""
    assert str(IdfFile.loads(one_line, ep_idd)) == str(IdfFile.loads(separate_lines, ep_idd))


@pytest.mark.parametrize(
    "line, expected",
    [
        ("  Zone,Z1;  ! My zone", ["  Zone,Z1;  ! My zone"]),
        ("  Zone,", ["  Zone,"]),
        ("Timestep,4;Zone,Z1;", ["Timestep,4;", "Zone,Z1;"]),
        ("Timestep,4;Zone,", ["Timestep,4;", "Zone,"]),
        ("Timestep,4;Zone,Z1;  ! My zone", ["Timestep,4;", "Zone,Z1;  ! My zone"]),
        ("Timestep,4;! something", ["Timestep,4;! something"]),
        ("A,1;B,2;C,3;", ["A,1;", "B,2;", "C,3;"]),
        ("Zone,Z1;  ! a; b; c", ["Zone,Z1;  ! a; b; c"]),  # ';' in a comment isn't a separator
    ],
)
def test_split_objects_on_one_line(line, expected):
    assert split_objects_on_one_line(line) == expected

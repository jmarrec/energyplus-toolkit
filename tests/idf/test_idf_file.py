"""Tests for IdfFile."""

from pathlib import Path

import pytest

from energyplus_parser.idd.idd_file import IddFile
from energyplus_parser.idd.idd_object import IddObject
from energyplus_parser.idf.idf_file import IdfFile
from energyplus_parser.idf.idf_object import IdfObject

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


def test_idf_file_str_inter_object_comment():
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


# ---------------------------------------------------------------------------
# Integration: real IDF serialisation with IDF_LEADING=2
# ---------------------------------------------------------------------------


def test_idf_file_str_1zone_uncontrolled_leading2(ep_idd):
    """Load the 1ZoneUncontrolled IDF, serialise with IDF_LEADING=2, and verify
    structural and spot-check properties of the output."""
    from energyplus_parser.idf import idf_constants

    idf_path = RESOURCES / "1ZoneUncontrolled-V26-1-0.idf"
    idf = IdfFile.load(idf_path, ep_idd)

    original_leading = idf_constants.IDF_LEADING
    try:
        idf_constants.IDF_LEADING = 2
        result = str(idf)
    finally:
        idf_constants.IDF_LEADING = original_leading

    lines = result.splitlines()

    # Header is preserved unchanged
    assert lines[0] == "!-Generator IDFEditor 1.34"

    # Every object line (not comment, not blank) starts with exactly 2 spaces
    object_type_lines = [
        line for line in lines if line and not line.startswith("!") and not line.startswith("  ")  # exclude field lines
    ]
    assert object_type_lines == [], "All non-comment non-blank lines must be indented by 2"

    # Field lines start with 4 spaces (IDF_LEADING=2 + IDF_INDENT=2)
    field_lines = [line for line in lines if line.startswith("    ") and ("!-" in line)]
    assert len(field_lines) > 0, "Expected field lines with 4-space indent"
    for line in field_lines:
        assert line.startswith("    "), f"Field line not indented by 4: {line!r}"

    # Spot-check: Version object
    version_block_start = next(i for i, l in enumerate(lines) if l == "  Version,")
    assert lines[version_block_start + 1] == "    26.1;                    !- Version Identifier"

    # Spot-check: Building object name field
    building_start = next(i for i, l in enumerate(lines) if l == "  Building,")
    assert lines[building_start + 1] == "    Simple One Zone (Wireframe DXF),  !- Name"

    # All 88 objects are present
    assert idf.num_objects() == 88

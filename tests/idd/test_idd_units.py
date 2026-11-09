"""Tests for the units table of the IDD header."""

from pathlib import Path

import pytest

from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.idd.idd_units import UnitPair, UnitsTable

RESOURCES = Path(__file__).parent.parent / "resources"

HEADER = """! Default IP conversions (no \\ip-units necessary)
!      m                      =>   ft                  3.28083989501312
!      C                      =>   F                   1.8 (plus 32)
!      m/s                    =>   ft/min              196.850393700787
!      m/s                    =>   miles/hr            2.2369362920544
!
! Other conversions supported (needs the \\ip-units code)
!
!      m                      =>   in                  39.3700787401575
!
! Units fields that are not translated
!      $
!      W/m2, W or deg C
! **************************************************************************
!      not part of the table
"""


def test_parse():
    table = UnitsTable.parse(HEADER)
    assert table is not None
    assert table.conversions == {
        "m": [UnitPair("m", "ft", 3.28083989501312), UnitPair("m", "in", 39.3700787401575)],
        "C": [UnitPair("C", "F", 1.8, 32.0)],
        "m/s": [UnitPair("m/s", "ft/min", 196.850393700787), UnitPair("m/s", "miles/hr", 2.2369362920544)],
    }
    # The first one listed in the default section
    assert table.defaults == {
        "m": UnitPair("m", "ft", 3.28083989501312),
        "C": UnitPair("C", "F", 1.8, 32.0),
        "m/s": UnitPair("m/s", "ft/min", 196.850393700787),
    }
    assert table.not_translated == {"$": UnitPair("$"), "W/m2, W or deg C": UnitPair("W/m2, W or deg C")}
    assert table.ip_units_for("m") == ["ft", "in"]
    assert table.is_known("$") and table.is_known("m") and not table.is_known("ft")


def test_parse_no_table():
    assert UnitsTable.parse("! Some header\n!      m  =>  ft  3.28\n") is None


def test_parse_malformed_conversion():
    with pytest.raises(ValueError, match="Malformed units conversion in the IDD header: 'm =>'"):
        UnitsTable.parse("! Default IP conversions (no \\ip-units necessary)\n!      m =>\n")


def test_parse_energyplus_idd():
    table = IddFile.load(RESOURCES / "V26-1-0-Energy+.idd").units_table()
    assert table is not None
    assert sum(len(pairs) for pairs in table.conversions.values()) == 119
    assert len(table.not_translated) == 36
    # Every SI unit with a conversion has a default
    assert table.defaults.keys() == table.conversions.keys()

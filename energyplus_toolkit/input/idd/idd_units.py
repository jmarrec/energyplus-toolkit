"""The units table in the header of Energy+.idd, which says which \\units and \\ip-units a field can have.

It has three sections, from ``! Default IP conversions`` to the ``! ****`` line that ends it::

    ! Default IP conversions (no \\ip-units necessary)
    !      m                      =>   ft                  3.28083989501312
    !      C                      =>   F                   1.8 (plus 32)
    ! Other conversions supported (needs the \\ip-units code)
    !      m                      =>   in                  39.3700787401575
    ! Units fields that are not translated
    !      $
"""

import re
from dataclasses import dataclass, field
from enum import Enum

RE_CONVERSION = re.compile(r"^(?P<si>.+?)\s*=>\s*(?P<ip>\S+)\s+(?P<factor>\S+)(?:\s+\(plus\s+(?P<offset>[^)]+)\))?$")


class UnitsSection(Enum):
    """A section of the table, by the start of its title line."""

    DEFAULT = "! Default IP conversions"
    OTHER = "! Other conversions supported"
    NOT_TRANSLATED = "! Units fields that are not translated"

    @staticmethod
    def from_title(line: str) -> "UnitsSection | None":
        return next((section for section in UnitsSection if line.startswith(section.value)), None)


@dataclass(frozen=True)
class UnitPair:
    si_units: str
    ip_units: str | None = None  # None if not translated
    conversion_factor: float = 1.0
    conversion_offset: float = 0.0


@dataclass
class UnitsTable:
    # By SI units, in the order of the table
    # This contains both the DEFAULT and OTHER sections, so it has all the conversions
    conversions: dict[str, list[UnitPair]] = field(default_factory=dict)

    # This is purely the first DEFAULT section
    defaults: dict[str, UnitPair] = field(default_factory=dict)

    not_translated: dict[str, UnitPair] = field(default_factory=dict)

    def is_known(self, si_units: str) -> bool:
        return si_units in self.conversions or si_units in self.not_translated

    def ip_units_for(self, si_units: str) -> list[str]:
        return [pair.ip_units for pair in self.conversions.get(si_units, []) if pair.ip_units is not None]

    @staticmethod
    def parse(header: str) -> "UnitsTable | None":
        """The table in an IDD header. None if it has none, eg an old IDD."""
        table = UnitsTable()
        section: UnitsSection | None = None
        for line in header.splitlines():
            if new_section := UnitsSection.from_title(line):
                section = new_section
            elif section is None:
                continue
            elif line.startswith("! *"):
                break
            elif not line.startswith("!      "):
                continue  # A blank "!" line
            elif section is UnitsSection.NOT_TRANSLATED:
                table._add_not_translated(entry=line[1:].strip())
            else:
                table._add_conversion(entry=line[1:].strip(), is_default_section=section is UnitsSection.DEFAULT)
        if not table.conversions and not table.not_translated:
            return None
        return table

    def _add_not_translated(self, entry: str) -> None:
        self.not_translated[entry] = UnitPair(si_units=entry)

    def _add_conversion(self, entry: str, is_default_section: bool) -> None:
        m = RE_CONVERSION.match(entry)
        if not m:
            raise ValueError(f"Malformed units conversion in the IDD header: '{entry}'")
        pair = UnitPair(
            si_units=m["si"],
            ip_units=m["ip"],
            conversion_factor=float(m["factor"]),
            conversion_offset=float(m["offset"]) if m["offset"] else 0.0,
        )
        self.conversions.setdefault(pair.si_units, []).append(pair)
        if is_default_section:
            # The first one listed is the default, eg m/s => ft/min, not miles/hr
            self.defaults.setdefault(pair.si_units, pair)

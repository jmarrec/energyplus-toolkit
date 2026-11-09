import re
from pathlib import Path

from energyplus_toolkit.input.idd.idd_constants import COMMENT_ONLY_OBJECT_NAME, COMMENT_ONLY_OBJECT_TEXT
from energyplus_toolkit.input.idd.idd_object import IddObject
from energyplus_toolkit.input.idd.idd_regex import RE_CLOSING_FIELD, RE_VERSION, RE_VERSION_OBJECT_NAME
from energyplus_toolkit.input.idd.idd_units import UnitsTable
from energyplus_toolkit.input.log_message import LogMessage


class IddFile:
    def __init__(self) -> None:
        # Version string required to be at top of any IddFile.
        self.version: str = ""
        # Build string which might be at the top of an IddFile.
        self.build: str = ""
        # The first comment block in an IddFile is its header.
        self.header: str = ""

        self.objects: list[IddObject] = [IddObject.load(group="", object_lines=[COMMENT_ONLY_OBJECT_TEXT])]

        # Cache for version object
        self._version_object: IddObject | None = None

    @staticmethod
    def load(path: Path) -> "IddFile":
        text = path.read_text(encoding="utf-8")
        return IddFile.fromString(text=text)

    @staticmethod
    def fromString(text: str) -> "IddFile":
        idd_file = IddFile()
        idd_file._parse(text=text)
        return idd_file

    def _parse(self, text: str) -> None:
        lines = text.splitlines()
        header_lines = []
        header_closed = False
        current_group = ""
        object_num = 0

        # Parse the first line as version
        if not lines:
            raise ValueError("Empty IDD file, no version found")
        first_line = lines.pop(0).strip()
        m = RE_VERSION.search(first_line)
        if m:
            self.version = m.group(1)
            header_lines.append(first_line)
        else:
            raise ValueError(f"Idd file does not contain version on first line: '{first_line}'")

        line_number = 0
        total_lines = len(lines)
        while line_number < total_lines:
            line = lines[line_number].strip()
            line_number += 1
            # print(f"a. {line_number}, {line}")
            if not line:
                # print(f"Header closed on {line_number}")
                header_closed = True
                continue
            elif line.startswith('!'):  # RE_COMMENT_ONLY_LINE.fullmatch(line):
                if not header_closed:
                    header_lines.append(line)
                # m := RE_BUILD.search(line):
                if 'IDD_BUILD' in line:
                    self.build = line.split('IDD_BUILD ')[1].strip()
                continue
            elif line.startswith(tag := '\\group'):
                header_closed = True
                current_group = line[len(tag) :].strip()
                if not current_group:
                    # The version line was popped, and line_number is already past this line
                    raise ValueError(f"\\group has no name on line {line_number + 1}")
                continue
            else:
                header_closed = True

                object_num += 1

                # Peek at object name
                # m = RE_LINE.search(line)
                # if not m:
                #     raise ValueError(f"Cannot determine object name: '{line}'")
                # object_name = m.group(1).strip()
                if ';' in line:
                    object_name = line.split(';')[0].strip()
                    found_closing_line = True
                elif ',' in line:
                    object_name = line.split(',')[0].strip()
                    found_closing_line = False
                else:
                    raise ValueError(f"Expected an object on line {line_number + 1}, got '{line}'")
                # print(f"{object_num=}, {object_name=}")

                # Collect full text of the object
                text_lines = [line]
                # The version line was popped, and line_number is already past this line
                object_line_number = line_number + 1
                # found_closing_line = bool(RE_OBJECT_NO_FIELDS.match(line)) or bool(RE_CLOSING_FIELD.match(line))

                while line_number < total_lines:
                    next_line = lines[line_number].strip()
                    line_number += 1
                    # print(line_number)
                    if found_closing_line and not next_line.startswith('\\'):  # RE_METADATA_COMMENT.match(next_line):
                        break
                    if next_line:
                        text_lines.append(next_line)
                        if RE_CLOSING_FIELD.fullmatch(next_line):
                            found_closing_line = True

                # try:
                obj = IddObject.load(group=current_group, object_lines=text_lines, line_number=object_line_number)
                assert obj.name == object_name
                self.objects.append(obj)
            # except Exception as e:
            #     raise ValueError(
            #         f"Unable to construct IddObject {object_name} from text:\n{'\n'.join(text_lines)}: {e}"
            #     )

        self.header = "\n".join(header_lines)

    def groups(self) -> set[str]:
        """Returns all groups in the file.

        eg: "" and "Simulation Parameters"
        """
        return {idd_obj.group for idd_obj in self.objects}

    def getObjectsInGroup(self, group: str) -> list[IddObject]:
        """Return all objects belonging to the specified group (case-insensitive)."""
        group_lower = group.lower()
        return [obj for obj in self.objects if obj.group.lower() == group_lower]

    def getObjects(self, object_regex: re.Pattern[str]) -> list[IddObject]:
        """Return all objects whose names match the given regex."""
        return [obj for obj in self.objects if object_regex.match(obj.name)]

    def versionObject(self) -> IddObject | None:
        """Return the Version object if present."""
        if self._version_object is not None:
            return self._version_object

        candidates = self.getObjects(RE_VERSION_OBJECT_NAME)
        if len(candidates) == 1:
            self._version_object = candidates[0]
        else:
            self._version_object = None

        return self._version_object

    def getObject(self, object_name: str) -> IddObject | None:
        """Return the first object whose name matches object_name (case-insensitive)."""
        name_lower = object_name.lower()
        for obj in self.objects:
            if obj.name.lower() == name_lower:
                return obj
        return None

    def requiredObjects(self) -> list[IddObject]:
        """Return all objects marked as required."""
        return [obj for obj in self.objects if obj.properties.required]

    def uniqueObjects(self) -> list[IddObject]:
        """Return all objects marked as unique."""
        return [obj for obj in self.objects if obj.properties.unique]

    def __repr__(self):
        return f"IddFile({len(self.objects)} objects)"

    def units_table(self) -> UnitsTable | None:
        """The units table of the header, None if it has none (eg an old IDD)."""
        return UnitsTable.parse(self.header)

    def validate(self) -> list[LogMessage]:
        """What is wrong with the objects of this file, which parsed fine. Units are checked against the units table of
        the header, if it has one."""
        units_table = self.units_table()
        return [message for obj in self.objects for message in obj.validate(units_table=units_table)]

    def __str__(self) -> str:
        """Return a formatted IDD file string representation."""
        lines: list[str] = [self.header, ""]
        current_group = ""

        for obj in self.objects:
            if obj.name == COMMENT_ONLY_OBJECT_NAME:
                continue
            if obj.group != current_group:
                current_group = obj.group
                lines.append(f"\\group {current_group}\n")
            lines.append(str(obj))

        # Each object ends with a blank line: not the file, which ends with exactly one newline (as pre-commit's
        # end-of-file-fixer wants it)
        return "\n".join(lines).rstrip("\n") + "\n"

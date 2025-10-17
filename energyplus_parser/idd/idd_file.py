import re
from pathlib import Path

from energyplus_parser.constants import COMMENT_ONLY_OBJECT_NAME, COMMENT_ONLY_OBJECT_TEXT
from energyplus_parser.idd.idd_object import IddObject
from energyplus_parser.idd.idd_regex import (
    RE_BUILD,
    RE_CLOSING_FIELD,
    RE_COMMENT_ONLY_LINE,
    RE_GROUP,
    RE_LINE,
    RE_METADATA_COMMENT,
    RE_OBJECT_NO_FIELDS,
    RE_VERSION,
    RE_VERSION_OBJECT_NAME,
)


class IddFile:
    def __init__(self) -> None:
        # Version string required to be at top of any IddFile.
        self.version: str = ""
        # Build string which might be at the top of an IddFile.
        self.build: str = ""
        # The first comment block in an IddFile is its header.
        self.header: str = ""

        self.objects: list[IddObject] = []

        # Cache for version object
        self._version_object: IddObject | None = None

    @staticmethod
    def load(path: Path) -> "IddFile":
        text = path.read_text()
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

        # Fake a comment-only object
        comment_only_object = IddObject.load(
            COMMENT_ONLY_OBJECT_NAME,
            current_group,
            COMMENT_ONLY_OBJECT_TEXT,
        )
        assert comment_only_object
        self.objects.append(comment_only_object)

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
            elif m := RE_BUILD.search(line):
                self.build = m.group(1)
                header_lines.append(line)
            elif RE_COMMENT_ONLY_LINE.fullmatch(line):
                if not header_closed:
                    header_lines.append(line)
                continue
            elif m := RE_GROUP.search(line):
                header_closed = True
                current_group = m.group(1).strip()
                # print(f"{current_group=}")
                continue
            else:
                header_closed = True

                object_num += 1

                # Peek at object name
                m = RE_LINE.search(line)
                if not m:
                    raise ValueError(f"Cannot determine object name: '{line}'")
                object_name = m.group(1).strip()
                # print(f"{object_num=}, {object_name=}")

                # Collect full text of the object
                text_lines = [line]
                found_closing_line = bool(RE_OBJECT_NO_FIELDS.match(line)) or bool(RE_CLOSING_FIELD.match(line))

                while line_number < total_lines:
                    next_line = lines[line_number].strip()
                    line_number += 1
                    # print(line_number)
                    if found_closing_line and not RE_METADATA_COMMENT.match(next_line):
                        break
                    if next_line:
                        text_lines.append(next_line)
                        if RE_CLOSING_FIELD.fullmatch(next_line):
                            found_closing_line = True

                object_text = "".join(text_lines)
                obj = IddObject.load(name=object_name, group=current_group, text=object_text)
                if obj:
                    self.objects.append(obj)
                else:
                    raise ValueError(f"Unable to construct IddObject from text:\n{object_text}")

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

        return "\n".join(lines) + "\n"

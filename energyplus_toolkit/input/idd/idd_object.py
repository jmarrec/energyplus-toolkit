import logging
import math
import re
from enum import StrEnum

from energyplus_toolkit.input.idd.idd_constants import BLOCK_INDENT
from energyplus_toolkit.input.idd.idd_field import FieldTypeChar, IddField
from energyplus_toolkit.input.idd.idd_regex import RE_FIELD_START
from energyplus_toolkit.input.log_message import LogLevel, LogMessage

LOG = logging.getLogger("IddObject")
LOG.setLevel(logging.INFO)


class IddObjectFormat(StrEnum):
    """\\format: how IDF Editor writes the object, with its "special format" option.

    The values are spelled as in the IDD, which isn't always as in its documentation ("compactSchedule", not
    "CompactSchedule", "FluidProperty", not "FluidProperties", "ViewFactor", not "ViewFactors").
    """

    SingleLine = "singleLine"  # all the fields on one line
    Vertices = "vertices"  # X, Y and Z of a vertex on one line
    CompactSchedule = "compactSchedule"
    FluidProperty = "FluidProperty"  # ten values per line
    ViewFactor = "ViewFactor"  # three fields per line
    Spectral = "Spectral"  # four fields per line

    @classmethod
    def parse(cls, text: str) -> "IddObjectFormat":
        """Case insensitive. Raises ValueError for an unknown format."""
        for member in cls:
            if member.value.lower() == text.lower():
                return member
        raise ValueError(f"Unknown \\format '{text}', expected one of: {', '.join(m.value for m in cls)}")


class IddObjectProperties:
    def __init__(self) -> None:
        # Returns the memo associated with this object.
        self.memo: str = ""

        # Returns true if this object must be unique within an individual IdfFile.
        self.unique: bool = False

        # True if this object is required for an IdfFile to be valid.
        self.required: bool = False

        # True if this object is obsolete.
        self.obsolete: bool = False
        self.obsolete_replacement: str = ""

        # Returns true if this object contains an IddField of type url.
        self.hasUrl: bool = False

        # True if this object is extensible
        self.extensible: bool = False

        # Returns the number of fields in this object's extensible group (zero if !extensible).
        self.numExtensible: int = 0
        # Returns the minimum number of extensible groups an IdfObject following this schema must have to be valid.
        self.numExtensibleGroupsRequired: int = 0

        # Formatting markup for this object, None if it has none. Suggests how to print certain types of IdfObjects.
        # For instance, many geometric objects have \\format vertices.
        self.format: IddObjectFormat | None = None

        # Minimum number of fields required for an IdfObject to be valid according to this schema.
        self.minFields: int = 0

        # Maximum number of fields allowed in IdfObjects following this schema.
        # Limits the number of allowable extensible groups
        self.maxFields: int | None = None

    def __str__(self) -> str:
        lines = []

        # Most important properties first
        if self.obsolete:
            replacement = f" New=>{self.obsolete_replacement}" if self.obsolete_replacement else ""
            lines.append(f"{BLOCK_INDENT}\\obsolete{replacement}")
        if self.unique:
            lines.append(f"{BLOCK_INDENT}\\unique-object")
        if self.required:
            lines.append(f"{BLOCK_INDENT}\\required-object")
        if self.hasUrl:
            lines.append(f"{BLOCK_INDENT}\\url-object")

        # Memo lines
        if self.memo:
            for line in self.memo.splitlines():
                lines.append(f"{BLOCK_INDENT}\\memo {line}")

        # Object field layout and formatting properties
        if self.extensible:
            lines.append(f"{BLOCK_INDENT}\\extensible:{self.numExtensible}")
        if self.minFields > 0:
            lines.append(f"{BLOCK_INDENT}\\min-fields {self.minFields}")
        if self.maxFields is not None:
            lines.append(f"{BLOCK_INDENT}\\max-fields {self.maxFields}")

        if self.format is not None:
            lines.append(f"{BLOCK_INDENT}\\format {self.format.value}")

        return "\n".join(lines)


def _compact_field_lines(fields: list[IddField], per_line: int = 10) -> list[str]:
    """Write fields declared without a name as compact lines: "  N1, N2, N3,  \\note ..." (";" after the last one)."""
    lines = []
    for i in range(0, len(fields), per_line):
        chunk = fields[i : i + per_line]
        ids = " ".join(f"{f.field_id}{';' if f.is_last_field else ','}" for f in chunk)
        notes = {f.properties.note for f in chunk}
        note = notes.pop() if len(notes) == 1 else ""
        lines.append(f"  {ids}  \\note {note}" if note else f"  {ids}")
    return lines


class IddObject:
    def __init__(self, group: str):
        self.name: str = ""
        self.group = group
        self.properties: IddObjectProperties = IddObjectProperties()
        # Non extensible fields
        self.fields: list[IddField] = []

        # Single extensible fields group
        self.extensible_fields: list[IddField] = []

        # This is ONLY to please the IDF Editor, but that's what it is...
        self._original_number_of_fields: int = 0

    def _format_error(self, error_msg: str) -> str:
        """Prefix ``error_msg`` with where it happened, like IddField._format_error."""
        return f"In '{self.name}': {error_msg}"

    def _parse_int(self, tag: str, value: str) -> int:
        """Parse the integer value of the ``tag`` property (\\min-fields, \\max-fields, \\extensible:)."""
        try:
            return int(value)
        except ValueError:
            raise ValueError(self._format_error(f"Invalid {tag} value '{value}'")) from None

    @staticmethod
    def load(group: str, object_lines: list[str]) -> "IddObject":
        idd_object = IddObject(group=group)
        idd_object._parse(object_lines=object_lines)
        return idd_object

    def _parse(self, object_lines: list[str]) -> None:
        if not object_lines:
            raise ValueError(f"No lines provided to parse for object in group '{self.group}'")

        object_lines = [x.strip() for x in object_lines]
        n_lines = len(object_lines)

        line_number = 0
        has_fields = ';' not in object_lines[line_number]
        self.name = object_lines[line_number].replace(',', ';').split(';', maxsplit=1)[0]

        line_number += 1

        if n_lines == 1:
            return

        found_fields_start = False

        # Process object: line_number is 1 already
        while line_number < n_lines:
            line = object_lines[line_number]
            line_number += 1

            if line.startswith('\\memo'):
                memo_text = line[len('\\memo') :].strip()
                if not memo_text:
                    LOG.info(self._format_error(f"\\memo line is empty: '{line}', discarding it"))
                elif self.properties.memo:
                    self.properties.memo += "\n" + memo_text
                else:
                    self.properties.memo = memo_text
            elif line.startswith('\\unique-object'):
                self.properties.unique = True
            elif line.startswith('\\required-object'):
                self.properties.required = True
            elif line.startswith('\\obsolete'):
                self.properties.obsolete = True
                # usage, if a replacement is available:
                #       \obsolete New=>[New object name]
                #   usage, if no replacement is available:
                #       \obsolete New=>deleted
                m = re.match(r"\\obsolete\s+New=>\s*(\S.*?)\s*$", line)
                if m:
                    self.properties.obsolete_replacement = m.group(1).strip()
                else:
                    raise ValueError(self._format_error(f"\\obsolete line is malformed: '{line}'"))
            elif line.startswith('\\url-object'):
                self.properties.hasUrl = True
            elif line.startswith(tag := '\\min-fields'):
                min_fields_str = line[len(tag) :].strip()
                self.properties.minFields = self._parse_int(tag=tag, value=min_fields_str)
            elif line.startswith(tag := '\\max-fields'):
                max_fields_str = line[len(tag) :].strip()
                self.properties.maxFields = self._parse_int(tag=tag, value=max_fields_str)
            elif line.startswith(tag := '\\extensible:'):
                num_extensible_str = line[len(tag) :].strip().split(" ")[0]
                self.properties.extensible = True
                self.properties.numExtensible = self._parse_int(tag=tag, value=num_extensible_str)
            elif line.startswith(tag := '\\format'):
                try:
                    self.properties.format = IddObjectFormat.parse(line[len(tag) :].strip())
                except ValueError as exc:
                    raise ValueError(self._format_error(str(exc))) from None
            elif has_fields and line.startswith('A') or line.startswith('N'):
                found_fields_start = True
                break
            else:
                raise ValueError(self._format_error(f"Unknown property line '{line}'"))

        if has_fields and not found_fields_start:
            raise ValueError(self._format_error("No fields found"))

        found_begin_extensible = False

        start_index = line_number - 1
        expanded_lines = []
        unnamed_ids: set[str] = set()  # fields declared without a \field name, eg "N1, N2, N3,  \note ..."
        for line in object_lines[start_index:]:
            # Only before the properties: a \note can mention a field, eg "(N13, default 3.342V)"
            matches = list(RE_FIELD_START.finditer(line.split("\\")[0]))
            self._original_number_of_fields += len(matches)
            if len(matches) == 0 or (len(matches) == 1 and "\\field" in line):
                expanded_lines.append(line)
                continue

            # Extract tail (anything after the last field match)
            last_match = matches[-1]
            tail = line[last_match.end() :].strip()

            # Split multi-field lines: keep only field ids, ignore tail like \note ...
            for match in matches:
                field_id = line[match.start() : match.end()].strip()  # drop trailing comma/semicolon
                unnamed_ids.add(field_id[:-1].strip())
                expanded_lines.append(f"{field_id} \\field {field_id[:-1]}")
                expanded_lines.append(tail)

        object_lines = object_lines[:start_index] + expanded_lines
        n_lines = len(object_lines)

        while line_number < n_lines:
            line = object_lines[line_number]

            if line.startswith('A') or line.startswith('N') or not line:
                end_index = line_number
                field_lines = object_lines[start_index:end_index]
                field = IddField.load(objectName=self.name, field_lines=field_lines)
                found_begin_extensible = self._add_field(field, found_begin_extensible)
                start_index = line_number

            if found_begin_extensible and len(self.extensible_fields) == self.properties.numExtensible:
                # Stop processing more fields and ensure we do not process the last
                start_index = n_lines + 1
                self.extensible_fields[-1].is_last_field = True
                break

            line_number += 1

        # process last field if needed
        if start_index < n_lines:
            field_lines = object_lines[start_index:]
            field = IddField.load(objectName=self.name, field_lines=field_lines)
            self._add_field(field, found_begin_extensible)

        for field in self.fields + self.extensible_fields:
            field.unnamed = field.field_id in unnamed_ids

        for field in self.extensible_fields:
            field.markExtensible()

        # Calculate extensible groups required
        if self.properties.extensible:
            if self.properties.minFields > 0:
                if self.properties.minFields > len(self.fields):
                    numerator = self.properties.minFields - len(self.fields)
                    denominator = self.properties.numExtensible
                    self.properties.numExtensibleGroupsRequired = math.ceil(numerator / denominator)

    def _add_field(self, field: IddField, found_begin_extensible: bool) -> bool:
        """Add a parsed field to the regular or the extensible fields.

        Returns whether the extensible group has started, with this field's \\begin-extensible or before it.
        """
        if field.properties.beginExtensible:
            if found_begin_extensible:
                raise ValueError(self._format_error("Multiple begin-extensible fields found"))
            if not self.properties.extensible:
                raise ValueError(field._format_error("Begin-extensible field found in a non-extensible object"))
            found_begin_extensible = True
        if found_begin_extensible:
            self.extensible_fields.append(field)
        else:
            self.fields.append(field)
        return found_begin_extensible

    def __repr__(self) -> str:
        return self.name

    def name_field_index(self) -> int | None:
        """Return the index of the name field, or None if absent.

        It takes field 0 and does IddField::is_name_field, and if so returns 0.  Otherwise it returns None.
        """
        if self.fields and self.fields[0].is_name_field():
            return 0
        return None

    def __str__(self) -> str:
        lines = []

        num_fields = len(self.fields) + len(self.extensible_fields)
        adding_extra = False
        if num_fields < self._original_number_of_fields:
            LOG.debug(
                self._format_error(
                    f"Adjusting number of fields from {num_fields} to original {self._original_number_of_fields}"
                )
            )
            adding_extra = True

        if not self.fields and not self.extensible_fields:
            lines.append(f"{self.name};")
            lines.append(str(self.properties))
            lines.append("")  # blank line at the end
        else:
            lines.append(f"{self.name},")
            lines.append(str(self.properties))

            # print regular fields, writing back the ones declared without a name compactly, as they were
            unnamed_run: list[IddField] = []
            for field in self.fields + [None]:  # type: ignore[list-item]
                if field is not None and field.unnamed:
                    unnamed_run.append(field)
                    continue
                lines.extend(_compact_field_lines(unnamed_run))
                unnamed_run = []
                if field is not None:
                    lines.append(str(field))

            # print extensible fields
            for i, field in enumerate(self.extensible_fields):
                if adding_extra:
                    prev_status = field.is_last_field
                    field.is_last_field = False
                lines.append(str(field))
                if adding_extra:
                    field.is_last_field = prev_status

            # Adjust number of fields to original if needed
            if adding_extra:

                assert self.extensible_fields, self._format_error(
                    "Cannot adjust number of fields if no extensible fields are defined"
                )
                numerator = self._original_number_of_fields - num_fields
                denominator = self.properties.numExtensible
                if numerator % denominator != 0:
                    raise ValueError(
                        self._format_error(
                            f"Cannot adjust number of fields to original {self._original_number_of_fields} "
                            f"with current fields {num_fields} and extensible group size {denominator}"
                        )
                    )
                extra_groups = int(numerator / denominator)
                # A and N fields are numbered separately: each group advances by its number of fields of that letter
                per_letter = {
                    letter: sum(1 for f in self.extensible_fields if f.field_id[0] == letter) for letter in "AN"
                }
                extra_field_ids = []
                for i in range(extra_groups):
                    for field in self.extensible_fields:
                        field_num = int(field.field_id[1:]) + (i + 1) * per_letter[field.field_id[0]]
                        field_id = f"{field.field_id[0]}{field_num}".ljust(
                            4 if self._original_number_of_fields > 100 else 3
                        )
                        extra_field_ids.append(field_id)

                # Break into chunks of 10
                chunk_size = 10
                for i in range(0, len(extra_field_ids), chunk_size):
                    chunk = extra_field_ids[i : i + chunk_size]
                    line = "  " + ", ".join(chunk) + ","
                    lines.append(line)
                lines[-1] = lines[-1].rstrip(',') + ';'  # change last line to end with semicolon

            lines.append("")  # blank line at the end

        return "\n".join(lines)

    def _validate_monotonic_field_ids(self) -> list[LogMessage]:
        """Field ids go up one by one from A1 and N1, separately. One message per gap: the count resumes from it.

        Only the first extensible group is known here: its repeats are renumbered from it when writing the object.
        """
        messages = []
        last_number = {FieldTypeChar.Alpha: 0, FieldTypeChar.Numeric: 0}
        for field in self.fields + self.extensible_fields:
            letter, number = field.field_id[0], field.field_id[1:]
            expected_id = f"{letter}{last_number[field.field_type_char] + 1}"
            if field.field_id != expected_id:
                msg = field._format_error(f"expected field ID {expected_id}, got {field.field_id}")
                messages.append(LogMessage(tool="idd-field-ids", loglevel=LogLevel.ERROR, message=msg))
            if number.isdigit():
                last_number[field.field_type_char] = int(number)
        return messages

    def _validate_extensible_fields(self) -> list[LogMessage]:
        if not self.properties.extensible:
            return []

        def error(msg: str) -> LogMessage:
            return LogMessage(tool="idd-extensible", loglevel=LogLevel.ERROR, message=self._format_error(msg))

        if not self.extensible_fields:
            return [error("Object is extensible but has no extensible fields")]

        messages = []
        if self.properties.numExtensible != len(self.extensible_fields):
            messages.append(
                error(
                    f"\\extensible:{self.properties.numExtensible} but {len(self.extensible_fields)} extensible fields"
                )
            )
        if not self.extensible_fields[-1].is_last_field:
            messages.append(error("Extensible fields do not end with a last field"))
        return messages

    def validate(self) -> list[LogMessage]:
        """What is wrong with this object and its fields, which parsed fine."""
        messages = self._validate_extensible_fields() + self._validate_monotonic_field_ids()
        for field in self.fields + self.extensible_fields:
            messages += field.validate()
        return messages

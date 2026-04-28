import logging
import math
from enum import IntEnum, StrEnum

from energyplus_parser.idd.idd_constants import BLOCK_INDENT, format_leading
from energyplus_parser.idd.idd_field import IddField
from energyplus_parser.idd.idd_regex import RE_FIELD_START, RE_NUMBER_AND_PRECEDING_SPACE

LOG = logging.getLogger("IddObject")
LOG.setLevel(logging.INFO)


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

        # Returns true if this object contains an IddField of type url.
        self.hasUrl: bool = False

        # True if this object is extensible
        self.extensible: bool = False

        # Returns the number of fields in this object's extensible group (zero if !extensible).
        self.numExtensible: int = 0
        # Returns the minimum number of extensible groups an IdfObject following this schema must have to be valid.
        self.numExtensibleGroupsRequired: int = 0

        # Formatting markup for this object. Often empty. Contains suggestions for printing certain
        # types of IdfObjects. For instance, many geometric objects have \\format vertices.
        self.format: str = ""

        # Minimum number of fields required for an IdfObject to be valid according to this schema.
        self.minFields: int = 0

        # Maximum number of fields allowed in IdfObjects following this schema.
        # Limits the number of allowable extensible groups
        self.maxFields: int | None = None

    def __str__(self) -> str:
        lines = []

        # Memo lines
        if self.memo:
            for line in self.memo.splitlines():
                lines.append(f"{BLOCK_INDENT}\\memo {line}")

        if self.unique:
            lines.append(f"{BLOCK_INDENT}\\unique-object")
        if self.required:
            lines.append(f"{BLOCK_INDENT}\\required-object")
        if self.obsolete:
            lines.append(f"{BLOCK_INDENT}\\obsolete")
        if self.hasUrl:
            lines.append(f"{BLOCK_INDENT}\\url-object")
        if self.extensible:
            lines.append(f"{BLOCK_INDENT}\\extensible:{self.numExtensible}")
        if self.format:
            lines.append(f"{BLOCK_INDENT}\\format {self.format}")
        if self.minFields > 0:
            lines.append(f"{BLOCK_INDENT}\\min-fields {self.minFields}")
        if self.maxFields is not None:
            lines.append(f"{BLOCK_INDENT}\\max-fields {self.maxFields}")

        return "\n".join(lines)


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
                if self.properties.memo:
                    self.properties.memo += "\n" + memo_text
                else:
                    self.properties.memo = memo_text
            elif line.startswith('\\unique-object'):
                self.properties.unique = True
            elif line.startswith('\\required-object'):
                self.properties.required = True
            elif line.startswith('\\obsolete'):
                self.properties.obsolete = True
            elif line.startswith('\\url-object'):
                self.properties.hasUrl = True
            elif line.startswith(tag := '\\min-fields'):
                min_fields_str = line[len(tag) :].strip()
                self.properties.minFields = int(min_fields_str)
            elif line.startswith(tag := '\\max-fields'):
                max_fields_str = line[len(tag) :].strip()
                self.properties.maxFields = int(max_fields_str)
            elif line.startswith(tag := '\\extensible:'):
                num_extensible_str = line[len(tag) :].strip().split(" ")[0]
                self.properties.extensible = True
                self.properties.numExtensible = int(num_extensible_str)
            elif line.startswith(tag := '\\format'):
                format_text = line[len(tag) :].strip()
                self.properties.format = format_text
            elif has_fields and line.startswith('A') or line.startswith('N'):
                found_fields_start = True
                break
            else:
                raise ValueError(f"Unknown property line '{line}' in object '{self.name}'")

        if has_fields and not found_fields_start:
            raise ValueError(f"No fields found in object '{self.name}'")

        found_begin_extensible = False

        start_index = line_number - 1
        expanded_lines = []
        for line in object_lines[start_index:]:
            matches = list(RE_FIELD_START.finditer(line))
            self._original_number_of_fields += len(matches)
            if len(matches) <= 1:
                expanded_lines.append(line)
                continue

            # Extract tail (anything after the last field match)
            last_match = matches[-1]
            tail = line[last_match.end() :].strip()

            # Split multi-field lines: keep only field ids, ignore tail like \note ...
            for match in matches:
                field_id = line[match.start() : match.end()].strip()  # drop trailing comma/semicolon
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

                if field.properties.beginExtensible:
                    if found_begin_extensible:
                        raise ValueError(f"Multiple begin-extensible fields found in object '{self.name}'")
                    if self.properties.extensible:
                        found_begin_extensible = True
                    else:
                        raise ValueError(
                            f"Begin-extensible field found in non-extensible object '{self.name}' for field '{field.name}'"
                        )
                if found_begin_extensible:
                    # Remove number from field name
                    field.name = RE_NUMBER_AND_PRECEDING_SPACE.sub("", field.name, count=1).strip()
                    self.extensible_fields.append(field)
                else:
                    self.fields.append(field)
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
            if found_begin_extensible:
                self.extensible_fields.append(field)
            else:
                self.fields.append(field)

        # Calculate extensible groups required
        if self.properties.extensible:
            if self.properties.minFields > 0:
                if self.properties.minFields > len(self.fields):
                    numerator = self.properties.minFields - len(self.fields)
                    denominator = self.properties.numExtensible
                    self.properties.numExtensibleGroupsRequired = math.ceil(numerator / denominator)

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        lines = []

        num_fields = len(self.fields) + len(self.extensible_fields)
        adding_extra = False
        if num_fields < self._original_number_of_fields:
            LOG.debug(
                f"Adjusting number of fields for object '{self.name}' from {num_fields} to original "
                f"{self._original_number_of_fields}"
            )
            adding_extra = True

        if not self.fields and not self.extensible_fields:
            lines.append(f"{self.name};")
            lines.append(str(self.properties))
            lines.append("")  # blank line at the end
        else:
            lines.append(f"{self.name},")
            lines.append(str(self.properties))

            # print regular fields
            for i, field in enumerate(self.fields):
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

                assert self.extensible_fields, "Cannot adjust number of fields if no extensible fields are defined"
                numerator = self._original_number_of_fields - num_fields
                denominator = self.properties.numExtensible
                if numerator % denominator != 0:
                    raise ValueError(
                        f"Cannot adjust number of fields to original {self._original_number_of_fields} "
                        f"with current fields {num_fields} and extensible group size {denominator}"
                    )
                extra_groups = int(numerator / denominator)
                extra_field_ids = []
                for i in range(extra_groups):
                    for field in self.extensible_fields:
                        field_num = int(field.field_id[1:]) + i + 1
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

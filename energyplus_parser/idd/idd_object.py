import logging
import math
from enum import IntEnum, StrEnum

from energyplus_parser.constants import BLOCK_INDENT, format_leading
from energyplus_parser.idd.idd_field import IddField
from energyplus_parser.idd.idd_regex import (
    RE_COMMENT_ONLY_LINE,
    RE_EXTENSIBLE_PROPERTY,
    RE_FIELD,
    RE_FIELD_START,
    RE_FORMAT_PROPERTY,
    RE_HASURL_PROPERTY,
    RE_LINE,
    RE_MAX_FIELDS_PROPERTY,
    RE_MEMO_PROPERTY,
    RE_METADATA_COMMENT,
    RE_MIN_FIELDS_PROPERTY,
    RE_NAME,
    RE_NUMBER_AND_PRECEDING_SPACE,
    RE_OBJECT_AND_FIELDS,
    RE_OBJECT_NO_FIELDS,
    RE_OBSOLETE_PROPERTY,
    RE_REQUIRED_OBJECT_PROPERTY,
    RE_UNIQUE_PROPERTY,
    RE_WHITESPACE_ONLY_BLOCK,
)

LOG = logging.getLogger("IddObject")
LOG.setLevel(logging.INFO)


class IddObjectProperties:
    def __init__(self):
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
    def __init__(self, name: str, group: str):
        self.name = name
        self.group = group
        self.properties: IddObjectProperties = IddObjectProperties()
        # Non extensible fields
        self.fields: list[IddField] = []

        # Single extensible fields group
        self.extensible_fields: list[IddField] = []

    def load(name: str, group: str, text: str):
        idd_object = IddObject(name=name, group=group)
        idd_object._parse(text=text)
        return idd_object

    def _parse(self, text: str) -> "IddObject":
        if m := RE_OBJECT_AND_FIELDS.search(text):
            # find and parse the object text
            object_text, fields_text = m.groups()
            self._parseObject(text=object_text)

            # find and parse the fields text
            self._parseFields(fields_text)

        elif RE_OBJECT_NO_FIELDS.fullmatch(text):
            # there are no fields in this object, it is all object text
            self._parseObject(text)

        else:
            # error
            raise ValueError(f"Unexpected pattern '{text}' found in object '{self.name}'")

        # remove existing extensible fields and add them to the extensible list
        if self.properties.extensible:
            self._makeExtensible()

    def _makeExtensible(self) -> None:
        num_extensible = self.properties.numExtensible

        # check that num_extensible > 0
        if num_extensible == 0:
            print(f"Error: Extensible length 0 in object '{self.name}'")
            return

        # find the begin extensible field, there should be only one
        extensible_begin_idx = None
        for idx, field in enumerate(self.fields):
            if field.properties.beginExtensible:
                extensible_begin_idx = idx
                break

        # no extensible begin found
        if extensible_begin_idx is None:
            print(f"Error: No begin-extensible field detected in object '{self.name}'")
            return

        # extensible begin is too close to the end of the field list
        if extensible_begin_idx + num_extensible > len(self.fields):
            print(f"Error: Extensible fields begin too close to end of fields in object '{self.name}'")
            return

        # copy extensible fields
        self.extensible_fields = self.fields[extensible_begin_idx : extensible_begin_idx + num_extensible]

        # remove all the extensible fields from the field list
        self.fields = self.fields[:extensible_begin_idx]

        # replace names of extensible fields so they do not contain numbers
        # e.g., "Vertex 1 X-coordinate" -> "Vertex X-coordinate"
        for field in self.extensible_fields:
            field_name = field.name
            # Using RE_NUMBER_AND_PRECEDING_SPACE from your RE_XXX definitions
            field_name = RE_NUMBER_AND_PRECEDING_SPACE.sub("", field_name, count=1)
            field_name = field_name.strip()
            field.name = field_name

        # figure out numExtensibleGroupsRequired
        if self.properties.minFields > 0:
            min_fields = self.properties.minFields
            if min_fields > len(self.fields):
                numerator = min_fields - len(self.fields)
                denominator = num_extensible
                self.properties.numExtensibleGroupsRequired = math.ceil(numerator / denominator)

    def _parseObject(self, text: str) -> None:
        # Find object name and initial properties text
        m = RE_LINE.search(text)
        if m:
            object_name = m.group(1).strip()
            if self.name != object_name:
                raise ValueError(f"Object name '{object_name}' does not match expected '{self.name}'")

            properties_text = m.group(2).strip()
        else:
            raise ValueError(f"Could not determine object name from text '{text}'")

        # Parse all metadata/comments
        while True:
            meta_match = RE_METADATA_COMMENT.search(properties_text)
            if not meta_match:
                break

            this_property = meta_match.group(1).strip()
            self._parseProperty(this_property)

            properties_text = meta_match.group(2).strip()

        # Check remaining text is only whitespace or comments
        if not (RE_WHITESPACE_ONLY_BLOCK.fullmatch(properties_text) or RE_COMMENT_ONLY_LINE.fullmatch(properties_text)):
            raise ValueError(f"Could not process properties text '{properties_text}' in object '{self.name}'")

    def _parseProperty(self, text: str) -> None:
        not_handled = True

        m = RE_MEMO_PROPERTY.search(text)
        if m:
            memo = m.group(1).strip()
            if not self.properties.memo:
                self.properties.memo = memo
            else:
                self.properties.memo += "\n" + memo
            not_handled = False

        elif RE_UNIQUE_PROPERTY.fullmatch(text):
            self.properties.unique = True
            not_handled = False

        elif RE_REQUIRED_OBJECT_PROPERTY.fullmatch(text):
            self.properties.required = True
            not_handled = False

        elif RE_OBSOLETE_PROPERTY.fullmatch(text):
            self.properties.obsolete = True
            not_handled = False

        elif RE_HASURL_PROPERTY.fullmatch(text):
            self.properties.hasUrl = True
            not_handled = False

        elif m := RE_EXTENSIBLE_PROPERTY.search(text):
            self.properties.extensible = True
            self.properties.numExtensible = int(m.group(1))
            not_handled = False

        elif m := RE_FORMAT_PROPERTY.search(text):
            self.properties.format = m.group(1).strip()
            not_handled = False

        elif m := RE_MIN_FIELDS_PROPERTY.search(text):
            self.properties.minFields = int(m.group(1))
            not_handled = False

        elif m := RE_MAX_FIELDS_PROPERTY.search(text):
            self.properties.maxFields = int(m.group(1))
            not_handled = False

        if not_handled:
            raise ValueError(f"Unknown property text '{text}' in object '{self.name}'")

    def _parseFields(self, text: str) -> None:
        begin = 0
        end = len(text)

        match = RE_FIELD_START.search(text)
        if match:
            begin = match.start()
            if begin != 0:
                raise ValueError(
                    f"Could not process field text '{text}' in object '{self.name}', start is not where expected"
                )
        else:
            return

        while begin < end:
            # Search for the next field start after current position
            match = RE_FIELD_START.search(text, begin + 1)
            if match:
                field_end = match.start()
            else:
                field_end = end

            # Extract field text
            field_text = text[begin:field_end]
            begin = field_end

            # Try to find field name
            name_match = RE_NAME.search(field_text)
            if name_match:
                field_name = name_match.group(1).strip()
            else:
                type_match = RE_FIELD.search(field_text)
                if type_match:
                    field_type_char = type_match.group(1).strip()
                    field_type_number = type_match.group(2).strip()
                    field_name = field_type_char + field_type_number
                else:
                    raise ValueError(f"Cannot determine field name from text '{field_text}'")

            # Load the field
            field = IddField.load(field_name, field_text, self.name)
            if field is None:
                raise ValueError(f"Cannot parse IddField text '{field_text}'")

            self.fields.append(field)

        # Mark last field
        self.fields[-1].is_last_field = True

    def __repr__(self) -> str:
        return self.name

    def __str__(self) -> str:
        lines = []

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
                lines.append(str(field))

            lines.append("")  # blank line at the end

        return "\n".join(lines)

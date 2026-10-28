import logging
from enum import IntEnum, StrEnum

from energyplus_parser.idd.idd_constants import AUTOSIZE_VALUE, BLOCK_INDENT, format_leading

LOG = logging.getLogger("IddField")
LOG.setLevel(logging.INFO)


class IddFieldParseError(Exception):
    pass


class IddFieldType(StrEnum):
    """IDD Field type.

    alpha, numeric, various flavors of alpha providing links to other objects and files.
    """

    UnknownType = "unknown"
    IntegerType = "integer"
    RealType = "real"
    AlphaType = "alpha"
    ChoiceType = "choice"
    NodeType = "node"
    ObjectListType = "object-list"
    ExternalListType = "external-list"
    URLType = "url"
    HandleType = "handle"


class BoundTypes(IntEnum):
    Unbounded = -1
    InclusiveBound = 0
    ExclusiveBound = 1


class IddFieldProperties:
    def __init__(self) -> None:
        self.type: IddFieldType = IddFieldType.UnknownType

        # Field notes collected into one string
        self.note: str = ""

        # True if this field is required (must be filled in for the IdfObject to be valid).
        self.required: bool = False

        # True if the field data is autosizable.
        self.autosizable: bool = False

        # True if the field autocalculatable.
        self.autocalculatable: bool = False

        # True if the field value is case-sensitive.
        self.retaincase: bool = False

        # True if this field has been deprecated (should not be used, but is okay for legacy files).
        self.deprecated: bool = False

        # True if this field is the first in an extensible group.
        self.beginExtensible: bool = False

        # The EnergyPlus-format unit string for this field.
        # All data are assumed to be associated with these (typically SI) units
        self.units: str | None = None
        # IP units — for user-facing displays only, no effect on underlying data
        self.ipUnits: str | None = None

        # Minimum bound is non-existent (Unbounded), >= (InclusiveBound), or > (ExclusiveBound).
        self.minBoundType: BoundTypes = BoundTypes.Unbounded
        self.minBoundValue: float | None = None

        # Maximum bound is non-existent (Unbounded), <= (InclusiveBound), or < (ExclusiveBound).
        self.maxBoundType: BoundTypes = BoundTypes.Unbounded
        self.maxBoundValue: float | None = None

        # The default value as string
        self.stringDefault: str | None = None
        # The default value as float
        self.numericDefault: float | None = None

        # This field points to an IdfObject that is registered with one of the reference lists named
        # in this vector. The list names are defined by \\reference markup of name fields.
        self.objectLists: list[str] = []

        # This field specifies that the containing IdfObject belongs to the following reference lists.
        # This information can be used by other objects to point to (reference) this object using
        # \\object-list markup
        self.references: list[str] = []

        # This field specifies that the containing IdfObject belongs to the following reference-class-name lists.
        self.referenceClassNames: list[str] = []

        # This field points to a name registered in another file (typically the RDD file).
        # OpenStudio treats these fields as plain (unparsed) text
        self.externalLists: list[str] = []

    def __eq__(self, other):
        if not isinstance(other, IddFieldProperties):
            return NotImplemented
        return (
            self.type == other.type
            and self.note == other.note
            and self.required == other.required
            and self.autosizable == other.autosizable
            and self.autocalculatable == other.autocalculatable
            and self.retaincase == other.retaincase
            and self.deprecated == other.deprecated
            and self.beginExtensible == other.beginExtensible
            and self.units == other.units
            and self.ipUnits == other.ipUnits
            and self.minBoundType == other.minBoundType
            and self.minBoundValue == other.minBoundValue
            and self.maxBoundType == other.maxBoundType
            and self.maxBoundValue == other.maxBoundValue
            and self.stringDefault == other.stringDefault
            and self.numericDefault == other.numericDefault
            and self.objectLists == other.objectLists
            and self.references == other.references
            and self.referenceClassNames == other.referenceClassNames
            and self.externalLists == other.externalLists
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self) -> str:
        """Render this field's properties in IDD-style text."""
        lines: list[str] = []

        # Notes
        if self.note:
            for line in self.note.splitlines():
                lines.append(f"{BLOCK_INDENT}\\note {line}")

        # Type
        if self.type != IddFieldType.UnknownType:
            lines.append(f"{BLOCK_INDENT}\\type {self.type.value}")

        # Simple flags
        if self.required:
            lines.append(f"{BLOCK_INDENT}\\required-field")
        if self.autosizable:
            lines.append(f"{BLOCK_INDENT}\\autosizable")
        if self.autocalculatable:
            lines.append(f"{BLOCK_INDENT}\\autocalculatable")
        if self.retaincase:
            lines.append(f"{BLOCK_INDENT}\\retaincase")
        if self.deprecated:
            lines.append(f"{BLOCK_INDENT}\\deprecated")
        if self.beginExtensible:
            lines.append(f"{BLOCK_INDENT}\\begin-extensible")

        # Units
        if self.units:
            lines.append(f"{BLOCK_INDENT}\\units {self.units}")
        if self.ipUnits:
            lines.append(f"{BLOCK_INDENT}\\ip-units {self.ipUnits}")

        # Bounds
        if self.minBoundType == BoundTypes.InclusiveBound and self.minBoundValue is not None:
            lines.append(f"{BLOCK_INDENT}\\minimum {self.minBoundValue}")
        elif self.minBoundType == BoundTypes.ExclusiveBound and self.minBoundValue is not None:
            lines.append(f"{BLOCK_INDENT}\\minimum> {self.minBoundValue}")

        if self.maxBoundType == BoundTypes.InclusiveBound and self.maxBoundValue is not None:
            lines.append(f"{BLOCK_INDENT}\\maximum {self.maxBoundValue}")
        elif self.maxBoundType == BoundTypes.ExclusiveBound and self.maxBoundValue is not None:
            lines.append(f"{BLOCK_INDENT}\\maximum< {self.maxBoundValue}")

        # Defaults
        if self.stringDefault:
            lines.append(f"{BLOCK_INDENT}\\default {self.stringDefault}")

        # Lists
        for obj in self.objectLists:
            lines.append(f"{BLOCK_INDENT}\\object-list {obj}")
        for ref in self.references:
            lines.append(f"{BLOCK_INDENT}\\reference {ref}")
        for ref in self.referenceClassNames:
            lines.append(f"{BLOCK_INDENT}\\reference-class-name {ref}")
        for ext in self.externalLists:
            lines.append(f"{BLOCK_INDENT}\\external-list {ext}")

        return "\n".join(lines)


class IddKey:
    """Represents a choice key for an IddField of type 'choice'.

    This is currently just a string but it provides strong equality semantics.
    """

    def __init__(self, name: str, note: str = ""):
        self.name: str = name
        self.note: str = note

    def __eq__(self, other):
        if not isinstance(other, IddKey):
            return NotImplemented
        return self.name == other.name

    def __repr__(self):
        return self.name

    def __str__(self):
        return f"{BLOCK_INDENT}\\key {self.name}"


class IddField:
    def __init__(self, objectName: str):
        self.name: str = ""
        self.field_id: str = ""
        self.objectName: str = objectName  # Name of IddObject to which this field belongs
        self.properties: IddFieldProperties = IddFieldProperties()
        self.keys: list[IddKey] = []
        self.is_last_field: bool = False

    def _parse_property(self, text: str):
        if not text:
            return

        not_handled = True
        lower_text = text.lower()
        index = lower_text[0]

        # === a ===
        if index == 'a':
            if lower_text.startswith("autosizable"):
                self.properties.autosizable = True
                not_handled = False
            elif lower_text.startswith("autocalculatable"):
                self.properties.autocalculatable = True
                not_handled = False

        # === b ===
        elif index == 'b':
            if lower_text.startswith("begin-extensible"):
                self.properties.beginExtensible = True
                not_handled = False

        # === d ===
        elif index == 'd':
            if lower_text.startswith(tag := "default"):
                string_default = text[len(tag) :].split('!')[0].strip()
                self.properties.stringDefault = string_default
                not_handled = False

                if self.properties.type in [IddFieldType.IntegerType, IddFieldType.RealType]:
                    if any(x in lower_text for x in ['autosize', 'autocalculate']):
                        self.properties.numericDefault = AUTOSIZE_VALUE
                    else:
                        self.properties.numericDefault = float(string_default)

            elif lower_text.startswith("deprecated"):
                self.properties.deprecated = True
                not_handled = False

        # === e ===
        elif index == 'e':
            if lower_text.startswith(tag := "external-list"):
                external_list = text[len(tag) :].split('!')[0].strip()
                self.properties.externalLists.append(external_list)
                not_handled = False

        # === f ===
        elif index == 'f':
            if lower_text.startswith(tag := "field"):
                field_name = text[len(tag) :].split('!')[0].strip()
                not_handled = False
                if self.name != field_name:
                    raise ValueError(
                        f"Field name '{field_name}' does not match expected '{self.name}' "
                        f"in object '{self.objectName}'"
                    )

        # === i ===
        elif index == 'i':
            if lower_text.startswith(tag := "ip-units"):
                self.properties.ipUnits = text[len(tag) :].split('!')[0].strip()
                not_handled = False

        # === k ===
        elif index == 'k':
            if lower_text.startswith(tag := "key"):
                key_name = text[len(tag) :].split('!')[0].strip()
                if not key_name:
                    raise ValueError(f"Key name is empty in field '{self.name}' of object '{self.objectName}'")
                key_note = ""
                if '!' in text:
                    key_note = text.split('!')[1].strip()
                self.keys.append(IddKey(name=key_name, note=key_note))
                not_handled = False
        # === m ===
        elif index == 'm':
            if lower_text.startswith(tag := "minimum"):
                rest = text[len(tag) :].split('!')[0].strip()
                if rest.startswith('>'):
                    self.properties.minBoundType = BoundTypes.ExclusiveBound
                    rest = rest[1:].strip()
                else:
                    self.properties.minBoundType = BoundTypes.InclusiveBound
                self.properties.minBoundValue = float(rest)
                not_handled = False
            elif lower_text.startswith(tag := "maximum"):
                rest = text[len(tag) :].split('!')[0].strip()
                if rest.startswith('<'):
                    self.properties.maxBoundType = BoundTypes.ExclusiveBound
                    rest = rest[1:].strip()
                else:
                    self.properties.maxBoundType = BoundTypes.InclusiveBound
                self.properties.maxBoundValue = float(rest)
                not_handled = False

            elif lower_text.startswith("memo"):
                raise ValueError("Memo property is deprecated; use Note property instead.")
        # === n ===
        elif index == 'n':
            if lower_text.startswith(tag := "note"):
                note = text[len(tag) :].strip()
                if not self.properties.note:
                    self.properties.note = note
                else:
                    self.properties.note += "\n" + note
                not_handled = False

        # === o ===
        elif index == 'o':
            if lower_text.startswith(tag := "object-list"):
                object_list = text[len(tag) :].strip().split('!')[0].strip()
                self.properties.objectLists.append(object_list)
                not_handled = False

        # === r ===
        elif index == 'r':
            if lower_text.startswith("required-field"):
                self.required = True
                not_handled = False
            elif lower_text.startswith(tag := "reference-class-name"):
                reference = text[len(tag) :].split('!')[0].strip()
                self.properties.referenceClassNames.append(reference)
                not_handled = False
            elif lower_text.startswith(tag := "reference"):
                reference = text[len(tag) :].split('!')[0].strip()
                self.properties.references.append(reference)
                not_handled = False
            elif lower_text.startswith("retaincase"):
                self.properties.retaincase = True
                not_handled = False

        # === t ===
        elif index == 't':
            if lower_text.startswith(tag := "type"):
                field_type = text[len(tag) :].split('!')[0].strip()
                self.properties.type = IddFieldType(field_type)
                not_handled = False

        # === u ===
        elif index == 'u':
            if lower_text.startswith("unitsBasedOnField"):
                # intentionally ignored in C++
                not_handled = False
            elif lower_text.startswith(tag := "units"):
                self.properties.units = text[len(tag) :].split('!')[0].strip()
                # m = RE_UNITS_PROPERTY.search(text)
                not_handled = False

        # === if none matched ===
        if not_handled:
            raise ValueError(f"Unknown field property text '{text}' detected in field '{self.name}'")

    @staticmethod
    def from_field_id_only(objectName: str, field_id=str) -> "IddField":
        field_id = field_id.strip()
        field = IddField(objectName=objectName)
        field.field_id = field_id

        fieldTypeChar = field.field_id[0]

        # Determine type
        if fieldTypeChar.lower() == "a":
            field.properties.type = IddFieldType.AlphaType
        elif fieldTypeChar.lower() == "n":
            # Default numerics to real
            field.properties.type = IddFieldType.RealType
        else:
            raise IddFieldParseError(f"Unknown field type identifier found: '{fieldTypeChar}'")
        return field

    @staticmethod
    def load(objectName: str, field_lines: list[str]) -> "IddField":
        field = IddField(objectName=objectName)
        field._parse(field_lines=field_lines)
        return field

    def _parse(self, field_lines: list[str]) -> None:
        if not field_lines:
            raise ValueError(f"No lines provided to parse for field in object '{self.objectName}'")

        field_lines = [x.strip() for x in field_lines]
        n_lines = len(field_lines)

        line_number = 0
        self.is_last_field = ';' in field_lines[line_number]
        if '\\field' not in field_lines[line_number]:
            breakpoint()
            raise IddFieldParseError(f"First line of field does not contain '\\field': '{field_lines[line_number]}'")
        self.field_id = field_lines[line_number].replace(',', ';').split(';', maxsplit=1)[0]
        self.field_id = self.field_id.strip()

        field_name = field_lines[line_number].split('\\field ', maxsplit=1)[1].strip().split('!')[0].strip()
        self.name = field_name
        if field_name != self.name:
            raise ValueError(
                f"Field name '{field_name}' does not match expected '{self.name}' in object '{self.objectName}'"
            )

        line_number += 1

        fieldTypeChar = self.field_id[0]

        # Determine type
        if fieldTypeChar.lower() == "a":
            self.properties.type = IddFieldType.AlphaType
        elif fieldTypeChar.lower() == "n":
            # Default numerics to real
            self.properties.type = IddFieldType.RealType
        else:
            raise IddFieldParseError(f"Unknown field type identifier found: '{fieldTypeChar}'")

        # Parse each metadata comment line (\keyword ...)
        while line_number < n_lines:
            line = field_lines[line_number]
            line_number += 1
            if not line.startswith('\\'):
                break

            # Delegate actual parsing
            self._parse_property(text=line[1:])

        # After consuming all properties, the rest should be empty or comment
        while line_number < n_lines:
            line = field_lines[line_number]
            line_number += 1
            if not line or line.startswith('!'):
                continue
            raise IddFieldParseError(
                f"Unexpected content found after field properties: '{line}', "
                f"in field '{self.name}' of object '{self.objectName}'"
            )

        # Validation
        if self.properties.type == IddFieldType.ChoiceType and not self.keys:
            LOG.error(f"Field is of type choice but keys are empty: '{self.name}'")
        elif self.properties.type != IddFieldType.ChoiceType and self.keys:
            LOG.error(f"Field is not of type choice but has non-empty keys: '{self.name}'")

        if self.properties.type == IddFieldType.UnknownType:
            raise IddFieldParseError(f"Field is of unknown type after parsing: '{self.name}'")

        # If a field has a default value, it's not required
        if self.properties.stringDefault and self.properties.required:
            LOG.info(
                f"Field '{self.name}' of object '{self.objectName}' "
                f"is both required and has default value — setting required=False."
            )
            self.properties.required = False

    def is_name_field(self) -> bool:
        """Return True if this field represents the name of the object.

        Matches OpenStudio logic: a field is a name field if it has \\reference
        tags (and no \\object-list), OR if its name is literally "Name" and its
        type is alpha or node.
        """
        p = self.properties
        has_references = bool(p.references)
        has_object_lists = bool(p.objectLists)
        if has_references and not has_object_lists:
            return True
        return self.name.lower() == "name" and p.type in (IddFieldType.AlphaType, IddFieldType.NodeType)

    def __repr__(self):
        return (
            f"{format_leading(field_id=self.field_id, is_last_field=self.is_last_field)}"
            f"\\field {self.name}\n{self.properties}"
        )

    def __str__(self):
        parts = [self.__repr__()]
        for k in self.keys:
            parts.append(str(k))
        return "\n".join(parts)

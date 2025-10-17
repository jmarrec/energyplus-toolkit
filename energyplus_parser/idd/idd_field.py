import logging
from enum import IntEnum, StrEnum

from energyplus_parser.constants import BLOCK_INDENT, format_leading
from energyplus_parser.idd.idd_regex import (
    RE_AUTOMATIC_DEFAULT,
    RE_COMMENT_ONLY_LINE,
    RE_CONTENT_AND_COMMENT_LINE,
    RE_DEFAULT_PROPERTY,
    RE_EXTERNAL_LIST_PROPERTY,
    RE_FIELD,
    RE_IP_UNITS_PROPERTY,
    RE_KEY_PROPERTY,
    RE_MAX_EXCLUSIVE_PROPERTY,
    RE_MAX_INCLUSIVE_PROPERTY,
    RE_MEMO_PROPERTY,
    RE_METADATA_COMMENT,
    RE_MIN_EXCLUSIVE_PROPERTY,
    RE_MIN_INCLUSIVE_PROPERTY,
    RE_NAME_PROPERTY,
    RE_NOTE_PROPERTY,
    RE_OBJECT_LIST_PROPERTY,
    RE_REFERENCE_CLASS_NAME_PROPERTY,
    RE_REFERENCE_PROPERTY,
    RE_TYPE_PROPERTY,
    RE_UNITS_PROPERTY,
    RE_WHITESPACE_ONLY_BLOCK,
)

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
        # The EnergyPlus-format unit string indicating this field's IP units. No effect on underlying data; a suggestion for user-facing displays
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

    def __init__(self, name: str):
        self.name = name
        self.note: str = ""

    def __eq__(self, other):
        if not isinstance(other, IddKey):
            return NotImplemented
        return self.name == other.name

    def __repr__(self):
        return self.name

    def __str__(self):
        return f"{BLOCK_INDENT}\\key {self.name}"

    @staticmethod
    def load(name: str, text: str):
        key = IddKey(name=name)
        m = RE_CONTENT_AND_COMMENT_LINE.search(text)
        assert m, f"Key name could not be determined from text '{text}'"
        key_name = m.group(1).strip()
        if key_name != name:
            raise ValueError(f"Key name '{key_name}' does not match expected '{name}'")

        note = m.group(2)
        key.note = note
        return key


class IddField:
    def __init__(self, name: str, objectName: str):
        self.name: str = name
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
            if lower_text.startswith("default"):
                m = RE_DEFAULT_PROPERTY.search(text)
                assert m, f"Invalid default property line: {text}"
                string_default = m.group(1).strip()
                self.properties.stringDefault = string_default
                not_handled = False

                if self.properties.type in ("real", "integer"):
                    if not RE_AUTOMATIC_DEFAULT.match(text):
                        self.properties.numericDefault = float(string_default)
                    else:
                        self.properties.numericDefault = -9999.0

            elif lower_text.startswith("deprecated"):
                self.properties.deprecated = True
                not_handled = False

        # === e ===
        elif index == 'e':
            if lower_text.startswith("external-list"):
                m = RE_EXTERNAL_LIST_PROPERTY.search(text)
                assert m, f"Invalid external-list property line: {text}"
                external_list = m.group(1).strip()
                self.properties.externalLists.append(external_list)
                not_handled = False

        # === f ===
        elif index == 'f':
            if lower_text.startswith("field"):
                m = RE_NAME_PROPERTY.search(text)
                assert m, f"Invalid field name property: {text}"
                field_name = m.group(1).strip()
                not_handled = False
                if self.name != field_name:
                    raise ValueError(
                        f"Field name '{field_name}' does not match expected '{self.name}' "
                        f"in object '{self.objectName}'"
                    )

        # === i ===
        elif index == 'i':
            if lower_text.startswith("ip-units"):
                m = RE_IP_UNITS_PROPERTY.search(text)
                assert m, f"Invalid ip-units property: {text}"
                ip_units = m.group(1).strip()
                self.properties.ipUnits = ip_units
                not_handled = False

        # === k ===
        elif index == 'k':
            if lower_text.startswith("key"):
                m = RE_KEY_PROPERTY.search(text)
                assert m, f"Invalid key property: {text}"
                key_text = m.group(1)
                not_handled = False

                key_match = RE_CONTENT_AND_COMMENT_LINE.search(key_text)
                if key_match:
                    key_name = key_match.group(1).strip()

                    key = IddKey.load(key_name, key_text)
                    if key is not None:
                        self.keys.append(key)
                    else:
                        raise ValueError(f"Key could not be loaded from text '{key_text}'.")
                else:
                    raise ValueError(f"Key name could not be determined from text '{key_text}'.")
        # === m ===
        elif index == 'm':
            if lower_text.startswith("minimum"):
                m_exc = RE_MIN_EXCLUSIVE_PROPERTY.search(text)
                m_inc = RE_MIN_INCLUSIVE_PROPERTY.search(text)
                if m_exc:
                    self.properties.minBoundType = BoundTypes.ExclusiveBound
                    min_exclusive = m_exc.group(1).strip()
                    self.properties.minBoundValue = float(min_exclusive)
                    not_handled = False
                elif m_inc:
                    self.properties.minBoundType = BoundTypes.InclusiveBound
                    min_inclusive = m_inc.group(1).strip()
                    self.properties.minBoundValue = float(min_inclusive)
                    not_handled = False
            elif lower_text.startswith("maximum"):
                m_exc = RE_MAX_EXCLUSIVE_PROPERTY.search(text)
                m_inc = RE_MAX_INCLUSIVE_PROPERTY.search(text)
                if m_exc:
                    self.properties.maxBoundType = BoundTypes.ExclusiveBound
                    max_exclusive = m_exc.group(1).strip()
                    self.properties.maxBoundValue = float(max_exclusive)
                    not_handled = False
                elif m_inc:
                    self.properties.maxBoundType = BoundTypes.InclusiveBound
                    max_inclusive = m_inc.group(1).strip()
                    self.properties.maxBoundValue = float(max_inclusive)
                    not_handled = False
            elif lower_text.startswith("memo"):
                m = RE_MEMO_PROPERTY.search(text)
                assert m, f"Invalid memo property: {text}"
                memo = m.group(1).strip()
                if not self.properties.note:
                    self.properties.note = memo
                else:
                    self.properties.note += "\n" + memo
                not_handled = False

        # === n ===
        elif index == 'n':
            if lower_text.startswith("note"):
                m = RE_NOTE_PROPERTY.search(text)
                assert m, f"Invalid note property: {text}"
                note = m.group(1).strip()
                if not self.properties.note:
                    self.properties.note = note
                else:
                    self.properties.note += "\n" + note
                not_handled = False

        # === o ===
        elif index == 'o':
            if lower_text.startswith("object-list"):
                m = RE_OBJECT_LIST_PROPERTY.search(text)
                assert m, f"Invalid object-list property: {text}"
                object_list = m.group(1).strip()
                self.properties.objectLists.append(object_list)
                not_handled = False

        # === r ===
        elif index == 'r':
            if lower_text.startswith("required-field"):
                self.required = True
                not_handled = False
            elif lower_text.startswith("reference-class-name"):
                m = RE_REFERENCE_CLASS_NAME_PROPERTY.search(text)
                assert m, f"Invalid reference-class-name property: {text}"
                reference = m.group(1).strip()
                self.properties.referenceClassNames.append(reference)
                not_handled = False
            elif lower_text.startswith("reference"):
                m = RE_REFERENCE_PROPERTY.search(text)
                assert m, f"Invalid reference property: {text}"
                reference = m.group(1).strip()
                self.properties.references.append(reference)
                not_handled = False
            elif lower_text.startswith("retaincase"):
                self.properties.retaincase = True
                not_handled = False

        # === t ===
        elif index == 't':
            if lower_text.startswith("type"):
                m = RE_TYPE_PROPERTY.search(text)
                assert m, f"Invalid type property: {text}"
                field_type = m.group(1).strip()
                self.properties.type = IddFieldType(field_type)
                not_handled = False

        # === u ===
        elif index == 'u':
            if lower_text.startswith("unitsBasedOnField"):
                # intentionally ignored in C++
                not_handled = False
            elif lower_text.startswith("units"):
                m = RE_UNITS_PROPERTY.search(text)
                assert m, f"Invalid units property: {text}"
                units = m.group(1).strip()
                self.properties.units = units
                not_handled = False

        # === if none matched ===
        if not_handled:
            raise ValueError(f"Unknown field property text '{text}' detected in field '{self.name}'")

    @staticmethod
    def load(name: str, text: str, objectName: str) -> "IddField":
        field = IddField(name=name, objectName=objectName)
        field._parse(text=text)
        return field

    def _parse(self, text: str) -> None:

        # Match the field definition
        match = RE_FIELD.search(text)
        if not match:
            raise IddFieldParseError(f"Field text does not match expected pattern: '{text}'")

        fieldTypeChar, fieldTypeNumber, fieldProperties = match.groups()

        # Field ID (e.g. A1, N2, etc.)
        self.field_id = f"{fieldTypeChar}{fieldTypeNumber}"

        # Determine type
        if fieldTypeChar.lower() == "a":
            self.properties.type = IddFieldType.AlphaType
        elif fieldTypeChar.lower() == "n":
            # Default numerics to real
            self.properties.type = IddFieldType.RealType
        else:
            raise IddFieldParseError(f"Unknown field type identifier found: '{fieldTypeChar}'")

        # Parse each metadata comment line (\keyword ...)
        while True:
            match = RE_METADATA_COMMENT.search(fieldProperties)
            if not match:
                break

            # property like "required-field", "type", "default", etc.
            property_line = match.group(1).strip()
            remaining = match.group(2).strip()

            # Delegate actual parsing
            self._parse_property(text=property_line)

            fieldProperties = remaining

        # After consuming all properties, the rest should be empty or comment
        remaining = fieldProperties.strip()
        if not (RE_WHITESPACE_ONLY_BLOCK.match(remaining) or RE_COMMENT_ONLY_LINE.match(remaining)):
            raise IddFieldParseError(f"Unable to parse remaining fields: '{remaining}'")

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

    def __repr__(self):
        return f"{format_leading(field_id=self.field_id, is_last_field=self.is_last_field)}\\field {self.name}\n{self.properties}"

    def __str__(self):
        parts = [self.__repr__()]
        for k in self.keys:
            parts.append(str(k))
        return "\n".join(parts)

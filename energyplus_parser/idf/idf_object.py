import logging

from energyplus_parser.idd.idd_constants import COMMENT_ONLY_OBJECT_NAME
from energyplus_parser.idd.idd_object import IddObject, IddObjectFormat
from energyplus_parser.idf import idf_constants
from energyplus_parser.idf.idf_field import IdfField, IntegerField, NumericField, NumericMode, RealField

LOG = logging.getLogger("IdfObject")
LOG.setLevel(logging.INFO)


class IdfObjectError(ValueError):
    pass


class IdfObject:
    """Holds field data for one EnergyPlus IDF object instance.

    The schema (field names, types, bounds, defaults) comes from the paired
    IddObject.  Field values are stored as typed IdfField subclasses.

    Field indexing is 0-based and covers non-extensible fields first, then
    extensible groups in order:

        index 0 … n-1          →  fixed fields (idd_object.fields)
        index n … n+g-1        →  extensible group 0
        index n+g … n+2g-1     →  extensible group 1
        …                         (g = idd_object.properties.numExtensible)
    """

    def __init__(self, idd_object: IddObject) -> None:
        self.idd_object: IddObject = idd_object
        self.comment: str = ""
        # Fixed (non-extensible) fields, one per idd_object.fields entry.
        self._fields: list[IdfField] = [IdfField.from_idd_field(f) for f in idd_object.fields]
        # Each inner list is one extensible group, sized to numExtensible.
        self._extensible_groups: list[list[IdfField]] = []
        # Number of fixed fields included in serialisation.  Starts at minFields,
        # or 1 when minFields is not specified (matching OpenStudio behaviour).
        # Writing a field at a higher index extends this automatically.
        min_f = idd_object.properties.minFields
        self._num_active_fields: int = min_f if min_f > 0 else min(1, len(self._fields))
        self._min_active_fields: int = self._num_active_fields  # floor for resets

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _new_extensible_group(self) -> list[IdfField]:
        return [IdfField.from_idd_field(f) for f in self.idd_object.extensible_fields]

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, idd_object: IddObject, text: str) -> "IdfObject":
        """Parse an IDF object text block and return a populated IdfObject."""
        obj = cls(idd_object=idd_object)
        obj._parse(text)
        return obj

    def _parse(self, text: str) -> None:
        """Populate fields by parsing IDF object text.

        The text should contain the full object block, e.g.::

            ! optional preceding comment
            ObjectType,
              value1,  !- Field 1
              value2;  !- Field 2
        """
        comment_lines: list[str] = []
        tokens: list[str] = []  # [object_type, field1_value, field2_value, …]
        # Maps token index → user comment text (bare "!" only, not "!-").
        token_comments: dict[int, str] = {}

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("!"):
                # Collect as object comment if we haven't parsed any field value yet
                # (covers both pre-object comments and in-object pre-field comments).
                if len(tokens) < 2:
                    comment_lines.append(stripped)
                continue

            # Split off inline comment, keeping track of user comments (bare "!").
            user_comment: str | None = None
            if "!" in stripped:
                bang_idx = stripped.index("!")
                content = stripped[:bang_idx].strip()
                comment_str = stripped[bang_idx:]
                if not comment_str.startswith("!-"):
                    user_comment = comment_str[1:].strip()  # text after "! "
            else:
                content = stripped

            if not content:
                continue

            tokens_before = len(tokens)

            # Tokenise: each separator (, or ;) ends a field value.
            current = ""
            for ch in content:
                if ch in ",;":
                    tokens.append(current.strip())
                    current = ""
                else:
                    current += ch
            # Any trailing content after the last separator is ignored
            # (shouldn't happen in valid IDF).

            # Associate user comment with the last token added on this line.
            if user_comment is not None and len(tokens) > tokens_before:
                last_idx = len(tokens) - 1
                if last_idx == 0:
                    # Comment on the object-type line → treat as object comment.
                    comment_lines.append(f"! {user_comment}")
                else:
                    token_comments[last_idx] = user_comment

        self.comment = "\n".join(comment_lines)

        if not tokens:
            raise IdfObjectError(f"No parseable content found for object '{self.idd_object.name}'")

        object_type = tokens[0]
        if object_type.lower() != self.idd_object.name.lower():
            raise IdfObjectError(f"Expected object type '{self.idd_object.name}', got '{object_type}'")

        n_fixed = len(self._fields)
        n_ext = self.idd_object.properties.numExtensible

        for idd_field_index, value in enumerate(tokens[1:]):
            if idd_field_index < n_fixed:
                idf_field = self._fields[idd_field_index]
            elif self.idd_object.properties.extensible and n_ext > 0:
                ext_pos = idd_field_index - n_fixed
                group_index = ext_pos // n_ext
                field_index = ext_pos % n_ext
                if field_index == 0:
                    self._extensible_groups.append(self._new_extensible_group())
                idf_field = self._extensible_groups[group_index][field_index]
            else:
                LOG.warning(f"Extra field at index {idd_field_index} in '{self.idd_object.name}' — ignoring")
                continue

            if value:
                idf_field.setString(value)

            token_idx = idd_field_index + 1  # token 0 is object type
            if token_idx in token_comments:
                idf_field.comment = token_comments[token_idx]

        # After parsing, active fields = number of fixed fields seen in the text
        # (bounded by n_fixed), but never below the initial minFields value.
        n_fixed_parsed = min(len(tokens) - 1, n_fixed)
        self._num_active_fields = max(self._num_active_fields, n_fixed_parsed)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extend_active_fields(self, index: int) -> None:
        """Ensure fixed fields up to and including *index* are serialised."""
        if index < len(self._fields):
            self._num_active_fields = max(self._num_active_fields, index + 1)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def nameFieldIndex(self) -> int | None:
        """Return the index of the name field, delegating to the IddObject."""
        return self.idd_object.name_field_index()

    @property
    def name(self) -> str | None:
        """Return the value of the name field, or None if absent or empty."""
        idx = self.nameFieldIndex()
        if idx is None:
            return None
        return self.getString(idx, return_default=False) or None

    def nameString(self, return_default: bool = False) -> str:
        """Return the name field value, or an empty string if absent."""
        idx = self.nameFieldIndex()
        if idx is None:
            return ""
        return self.getString(idx, return_default=return_default) or ""

    def setName(self, value: str) -> None:
        """Set the name field value.  Raises if the object has no name field."""
        idx = self.nameFieldIndex()
        if idx is None:
            raise IdfObjectError(f"Object '{self.idd_object.name}' has no name field")
        self.setString(idx, value)

    def num_fields(self) -> int:
        """Total number of fields currently in this object (fixed + extensible)."""
        n_fixed = len(self._fields) if self._extensible_groups else self._num_active_fields
        return n_fixed + sum(len(g) for g in self._extensible_groups)

    def num_extensible_groups(self) -> int:
        return len(self._extensible_groups)

    # ------------------------------------------------------------------
    # Field access by index
    # ------------------------------------------------------------------

    def _get_field(self, index: int) -> IdfField:
        n_fixed = len(self._fields)
        if index < n_fixed:
            return self._fields[index]
        ext_index = index - n_fixed
        n_ext = self.idd_object.properties.numExtensible
        if n_ext == 0:
            raise IndexError(f"Index {index} out of range for non-extensible object '{self.idd_object.name}'")
        group_index = ext_index // n_ext
        field_index = ext_index % n_ext
        if group_index >= len(self._extensible_groups):
            raise IndexError(
                f"Index {index} out of range — only {len(self._extensible_groups)} "
                f"extensible group(s) present in object '{self.idd_object.name}'"
            )
        return self._extensible_groups[group_index][field_index]

    def get_value(self, index: int, return_default: bool = False) -> str | int | float | NumericMode | None:
        """Return the field value as its native Python type.

        Returns ``str`` for alpha/choice/node fields, ``int`` for integer fields,
        ``float`` for real fields, ``NumericMode`` when the field is set to
        autosize/autocalculate, and ``None`` when the field is unset (and
        *return_default* is False).
        """
        return self._get_field(index).value(return_default=return_default)

    def getString(self, index: int, return_default: bool = False) -> str | None:
        field = self._get_field(index)
        val = field.value(return_default=return_default)
        if val is None:
            return None
        return str(val)

    def setString(self, index: int, value: str) -> None:
        self._get_field(index).setString(value)
        self._extend_active_fields(index)

    def getDouble(self, index: int, return_default: bool = False) -> float | None:
        field = self._get_field(index)
        if not isinstance(field, NumericField):
            raise TypeError(f"Field {index} is not a numeric field")
        val = field.value(return_default=return_default)
        if val is None or isinstance(val, NumericMode):
            return None
        return float(val)

    def setDouble(self, index: int, value: float) -> None:
        field = self._get_field(index)
        if not isinstance(field, RealField):
            raise TypeError(f"Field {index} is not a RealField")
        field.setDouble(value)
        self._extend_active_fields(index)

    def getInt(self, index: int, return_default: bool = False) -> int | None:
        field = self._get_field(index)
        if not isinstance(field, IntegerField):
            raise TypeError(f"Field {index} is not an IntegerField")
        val = field.value(return_default=return_default)
        if val is None or isinstance(val, NumericMode):
            return None
        return int(val)

    def setInt(self, index: int, value: int) -> None:
        field = self._get_field(index)
        if not isinstance(field, IntegerField):
            raise TypeError(f"Field {index} is not an IntegerField")
        field.setInt(value)
        self._extend_active_fields(index)

    # ------------------------------------------------------------------
    # Extensible group management
    # ------------------------------------------------------------------

    def push_extensible_group(self, values: list[str] | None = None) -> list[IdfField]:
        """Append a new extensible group, optionally pre-populated with *values*.

        Returns the list of IdfField instances for the new group.
        """
        if not self.idd_object.properties.extensible:
            raise IdfObjectError(f"Object '{self.idd_object.name}' is not extensible")
        group = self._new_extensible_group()
        if values:
            for i, v in enumerate(values):
                if i < len(group) and v:
                    group[i].setString(v)
        self._extensible_groups.append(group)
        self._num_active_fields = len(self._fields)
        return group

    def get_extensible_group(self, group_index: int) -> list[IdfField]:
        """Return the IdfField list for the extensible group at *group_index*."""
        if group_index >= len(self._extensible_groups):
            raise IndexError(f"Extensible group index {group_index} out of range")
        return self._extensible_groups[group_index]

    def pop_extensible_group(self) -> list[IdfField]:
        """Remove and return the last extensible group."""
        if not self._extensible_groups:
            raise IdfObjectError("No extensible groups to pop")
        return self._extensible_groups.pop()

    def clear_extensible_groups(self) -> list[list[IdfField]]:
        """Remove all extensible groups and return them."""
        groups = self._extensible_groups[:]
        self._extensible_groups.clear()
        return groups

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        for field in self._fields:
            field.validate()
        for group in self._extensible_groups:
            for field in group:
                field.validate()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def __str__(self) -> str:
        lines: list[str] = []

        if self.idd_object.name == COMMENT_ONLY_OBJECT_NAME:
            if self.comment:
                return f"{self.comment}\n"

        if self.comment:
            lines.append(self.comment)

        active_fixed = (
            list(self._fields[: self._num_active_fields]) if not self._extensible_groups else list(self._fields)
        )
        all_fields: list[IdfField] = active_fixed + [f for g in self._extensible_groups for f in g]

        indent = " " * idf_constants.IDF_LEADING

        if not all_fields:
            lines.append(f"{indent}{self.idd_object.name};")
        elif self.idd_object.properties.format == IddObjectFormat.SingleLine:
            # value_text() is empty only for an empty field: 0 / 0.0 are kept
            vals = [f.value_text() for f in all_fields]
            # Trim trailing empty fields
            while len(vals) > 1 and not vals[-1]:
                vals.pop()
            lines.append(f"{indent}{self.idd_object.name},{','.join(vals)};")
        else:
            lines.append(f"{indent}{self.idd_object.name},")
            # Extensible fields are numbered by group, like in the IDD: "Vertex 1 X-coordinate", "Vertex 2 X-coordinate"
            entries: list[tuple[IdfField, str]] = [(f, f.idd_field.name) for f in active_fixed] + [
                (f, f.idd_field.name_for_group(i)) for i, group in enumerate(self._extensible_groups) for f in group
            ]
            for i, (field, name) in enumerate(entries):
                lines.append(field.text(is_last_field=i == len(entries) - 1, field_name=name))

        lines.append("")  # blank line at end
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"IdfObject({self.idd_object.name!r}, name={self.name!r})"

import logging
import re
from abc import ABC, abstractmethod
from enum import StrEnum

from energyplus_parser.idd.idd_constants import AUTOSIZE_VALUE
from energyplus_parser.idd.idd_field import BoundTypes, IddField, IddFieldProperties, IddFieldType
from energyplus_parser.idf import idf_constants
from energyplus_parser.idf.idf_constants import format_idf_field

LOG = logging.getLogger("IdfField")


class NumericMode(StrEnum):
    NORMAL = "Normal"
    AUTOSIZE = "Autosize"
    AUTOCALCULATE = "Autocalculate"


class FieldValidationError(ValueError):
    pass


class IdfField(ABC):
    def __init__(self, idd_field: IddField) -> None:
        self._value: str | float | int | None = None
        self._default_value: str | float | int | None = None
        self.idd_field: IddField = idd_field
        self._default_value = idd_field.properties.stringDefault
        self.is_last_field = idd_field.is_last_field
        self.comment: str | None = None  # user-provided field comment; None = use IDD field name

    @property
    def required(self):
        # A field with a default can be left blank, even if the IDD says it's \required-field
        props = self.idd_field.properties
        return props.required and not props.stringDefault

    @staticmethod
    def from_idd_field(idd_field) -> "IdfField":
        field_type = idd_field.properties.type

        field: IdfField
        if field_type == IddFieldType.AlphaType:
            field = AlphaField(idd_field=idd_field)
        elif field_type == IddFieldType.IntegerType:
            field = IntegerField(idd_field=idd_field)
        elif field_type == IddFieldType.RealType:
            field = RealField(idd_field=idd_field)
        elif field_type == IddFieldType.ChoiceType:
            if (idd_field.objectName.lower(), idd_field.name.lower()) == ("schedule:week:compact", "daytype list"):
                field = DayTypeListField(idd_field=idd_field)
            else:
                field = ChoiceField(idd_field=idd_field)
        elif field_type == IddFieldType.NodeType:
            field = NodeField(idd_field=idd_field)
        elif field_type == IddFieldType.ObjectListType:
            field = ObjectListField(idd_field=idd_field)
        elif field_type == IddFieldType.ExternalListType:
            field = ExternalListField(idd_field=idd_field)
        elif field_type == IddFieldType.URLType:
            field = URLField(idd_field=idd_field)
        elif field_type == IddFieldType.HandleType:
            field = HandleField(idd_field=idd_field)
        else:
            raise ValueError(f"Unknown field type: {field_type} for field {idd_field.name}")

        return field

    @abstractmethod
    def setString(self, value: str):
        pass

    @abstractmethod
    def validate(self):
        if self.required and self.value(return_default=True) is None:
            raise FieldValidationError("Required field with no default value")

    def value(self, return_default: bool = False) -> str | float | int | None:
        if self._value is not None:
            return self._value
        if return_default:
            return self._default_value
        return None

    def is_defaulted(self) -> bool:
        return self.value(return_default=False) is None

    def reset(self):
        if self.required and self.value(return_default=True) is None:
            raise FieldValidationError("Cannot reset a required field with no default value")
        self._value = None

    def value_text(self) -> str:
        """The value as written in the IDF ("" if the field is empty)."""
        v = self.value(return_default=False)
        return "" if v is None else str(v)

    def text(self, is_last_field: bool = False, field_name: str | None = None) -> str:
        """The field's IDF line. ``field_name`` (for the ``!-`` comment) defaults to the IDD field name."""
        return format_idf_field(
            value=self.value_text(),
            is_last_field=is_last_field,
            field_name=self.idd_field.name if field_name is None else field_name,
            comment=self.comment,
            units=self.idd_field.properties.units,
        )

    def __repr__(self) -> str:
        default_attr = " [defaulted]" if self.is_defaulted() else ""
        return f"{self.__class__.__name__}({self.value(return_default=True)}{default_attr})"

    def __str__(self) -> str:
        return self.text()


class AlphaField(IdfField):
    def __init__(self, idd_field: IddField) -> None:
        super().__init__(idd_field=idd_field)

    def setString(self, value: str):
        self._value = value.strip()

    def validate(self):
        super().validate()


class DayTypeListField(AlphaField):
    """Schedule:Week:Compact "DayType List": a choice field in the IDD, but EnergyPlus takes any text containing at
    least one day type, eg "For: Weekdays Holiday" (ScheduleManager.cc ProcessForDayTypes, and its schema generator
    drops the keys). It's kept as written."""

    # What ProcessForDayTypes searches for, in the upper-cased value
    DAY_TYPES = (
        "WEEKDAY",
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
        "WEEKEND",
        "SATURDAY",
        "SUNDAY",
        "CUSTOMDAY1",
        "CUSTOMDAY2",
        "ALLDAY",
        "HOLIDAY",
        "SUMMER",
        "WINTER",
        "ALLOTHERDAY",
    )

    def setString(self, value: str):
        v = value.strip()
        if v and not any(day in v.upper() for day in self.DAY_TYPES):
            raise FieldValidationError(f"Field '{self.idd_field.name}' - No valid day type in: {v}")
        self._value = v


class NumericField(IdfField):
    def __init__(self, idd_field: IddField) -> None:
        super().__init__(idd_field=idd_field)
        self._value: float | int | None = None

        self.autocalculatable: bool = False
        self.autosizable: bool = False
        self._mode: NumericMode = NumericMode.NORMAL

        self._default_value: float | int | None | NumericMode = None

        self.minimum_value: float | int | None = None
        self.min_bound_type: BoundTypes = BoundTypes.Unbounded

        self.maximum_value: float | int | None = None
        self.max_bound_type: BoundTypes = BoundTypes.Unbounded

        props: IddFieldProperties = self.idd_field.properties

        self.autocalculatable = props.autocalculatable
        self.autosizable = props.autosizable

        if props.numericDefault == AUTOSIZE_VALUE:
            if self.autocalculatable:
                self._default_value = NumericMode.AUTOCALCULATE
            elif self.autosizable:
                self._default_value = NumericMode.AUTOSIZE
        else:
            self._default_value = props.numericDefault

        self.minimum_value = props.minBoundValue
        self.min_bound_type = props.minBoundType

        self.maximum_value = props.maxBoundValue
        self.max_bound_type = props.maxBoundType

    def value(self, return_default: bool = False) -> str | float | int | None | NumericMode:
        if self._mode == NumericMode.NORMAL:
            return super().value(return_default=return_default)

        return self._mode

    def autocalculate(self):
        # EnergyPlus's InputProcessor treats "Autosize" and "Autocalculate" as synonyms, so accept it
        # on an autosizable-only field, but switch it to the keyword the field actually supports.
        if not self.autocalculatable:
            if not self.autosizable:
                raise FieldValidationError("Autocalculate not allowed")
            LOG.warning(f"Field '{self.idd_field.name}' is autosizable, not autocalculatable — switching to Autosize")
            self.autosize()
            return
        self._mode = NumericMode.AUTOCALCULATE
        self._value = None

    def autosize(self):
        if not self.autosizable:
            if not self.autocalculatable:
                raise FieldValidationError("Autosize not allowed")
            LOG.warning(
                f"Field '{self.idd_field.name}' is autocalculatable, not autosizable — switching to Autocalculate"
            )
            self.autocalculate()
            return
        self._mode = NumericMode.AUTOSIZE
        self._value = None

    def is_autosized(self) -> bool:
        return self.value(return_default=True) == NumericMode.AUTOSIZE

    def is_autocalculated(self) -> bool:
        return self.value(return_default=True) == NumericMode.AUTOCALCULATE

    def setString(self, value: str):
        v = value.strip().lower()

        if not v:
            if self.required:
                raise FieldValidationError("Cannot set required numeric field to empty value")
            self._value = None
            self._mode = NumericMode.NORMAL
            return

        if v == "autosize":
            self.autosize()
            return

        if v == "autocalculate":
            self.autocalculate()
            return

        parsed = self._parse_number(value)
        self._validate_range(parsed)
        self._mode = NumericMode.NORMAL
        self._value = parsed

    def validate(self):
        super().validate()

        if self._mode == NumericMode.NORMAL and self._value is not None:
            self._validate_range(self._value)

    @classmethod
    @abstractmethod
    def _parse_number(cls, value: str) -> int | float:
        """Parse a string into a number of the appropriate type.

        This should throw FieldValidationError if the string cannot be parsed.
        """
        pass

    def _validate_range(self, value: int | float):
        if self.minimum_value is not None:
            if self.min_bound_type == BoundTypes.InclusiveBound:
                if value < self.minimum_value:
                    raise FieldValidationError(f"{value} must be >= {self.minimum_value}")
            elif self.min_bound_type == BoundTypes.ExclusiveBound:
                if value <= self.minimum_value:
                    raise FieldValidationError(f"{value} must be > {self.minimum_value}")

        if self.maximum_value is not None:
            if self.max_bound_type == BoundTypes.InclusiveBound:
                if value > self.maximum_value:
                    raise FieldValidationError(f"{value} must be <= {self.maximum_value}")
            elif self.max_bound_type == BoundTypes.ExclusiveBound:
                if value >= self.maximum_value:
                    raise FieldValidationError(f"{value} must be < {self.maximum_value}")

    def reset(self):
        if self.required and self.value(return_default=True) is None:
            raise FieldValidationError("Cannot reset a required field with no default value")
        self._value = None
        self._mode = NumericMode.NORMAL


class IntegerField(NumericField):
    def __init__(self, idd_field: IddField) -> None:
        super().__init__(idd_field=idd_field)
        self._value: int | None = None
        if self.minimum_value is not None:
            self.minimum_value = int(self.minimum_value)
        if self.maximum_value is not None:
            self.maximum_value = int(self.maximum_value)
        if isinstance(self._default_value, float):
            self._default_value = int(self._default_value)

    def setInt(self, value: int) -> None:
        if not isinstance(value, (float, int)):
            raise TypeError("IntegerField value must be an int")
        # Accept a float with no fractional part, eg 512.0, but don't truncate 512.5
        if isinstance(value, float) and not value.is_integer():  # also False for nan and inf
            raise FieldValidationError(f"Invalid integer: {value}")
        v = int(value)
        self._validate_range(value=v)
        self._value = v
        self._mode = NumericMode.NORMAL

    @classmethod
    def _parse_number(cls, value: str) -> int:
        """Parse an integer, also accepting a float with no fractional part, eg "512.0".

        Anything else is invalid. This is stricter than EnergyPlus, which rounds any number (2.1 -> 2).
        """
        if "_" in value:  # Python's int() and float() accept "1_000", IDF doesn't
            raise FieldValidationError(f"Invalid integer: {value}")
        try:
            return int(value)
        except ValueError:
            pass
        try:
            as_float = float(value)
        except ValueError:
            raise FieldValidationError(f"Invalid integer: {value}") from None
        if not as_float.is_integer():  # also False for nan and inf
            raise FieldValidationError(f"Invalid integer: {value}")
        return int(as_float)


class RealField(NumericField):
    def __init__(self, idd_field: IddField) -> None:
        super().__init__(idd_field=idd_field)
        self._value: float | None = None
        self._written_as_integer = False  # set by setString, see idf_constants.IDF_KEEP_INTEGER_REALS

    def setString(self, value: str):
        super().setString(value)
        self._written_as_integer = self._value is not None and re.fullmatch(r"[+-]?\d+", value.strip()) is not None

    def setDouble(self, value: float) -> None:
        if not isinstance(value, (float, int)):
            raise TypeError("RealField value must be a float")
        v = float(value)
        self._validate_range(value=v)
        self._value = v
        self._mode = NumericMode.NORMAL
        self._written_as_integer = False

    def value_text(self) -> str:
        v = self.value(return_default=False)
        keep_integer = (
            idf_constants.IDF_KEEP_INTEGER_REALS
            or self.idd_field.name.lower() in idf_constants.IDF_KEEP_INTEGER_REALS_FIELDS
        )
        if keep_integer and self._written_as_integer and isinstance(v, float):
            return str(int(v))
        return super().value_text()

    @classmethod
    def _parse_number(cls, value: str) -> float:
        try:
            return float(value)
        except ValueError:
            raise FieldValidationError(f"Invalid float: {value}")


class ChoiceField(IdfField):
    def __init__(self, idd_field: IddField) -> None:
        super().__init__(idd_field=idd_field)

        self.valid_choices: set[str] = {k.name for k in idd_field.keys}
        self._canonical_map: dict[str, str] = {k.lower(): k for k in self.valid_choices}
        self.is_boolean: bool = self._canonical_map.keys() == {'no', 'yes'}

        self._default_value: str | None = idd_field.properties.stringDefault

    def setString(self, value: str):
        v = value.strip()
        v = self._canonical_validate_choice(value=v)
        self._value = v

    def setBool(self, value: bool):
        if not self.is_boolean:
            raise FieldValidationError("This choice field '{self.idd_field.name}' is not a boolean field")
        self._value = "Yes" if value else "No"

    def validate(self):
        super().validate()
        if self._value is not None:
            self._canonical_validate_choice(value=self._value)

    def _canonical_validate_choice(self, value: str):
        v = self._canonical_map.get(value.lower(), None)
        if v is None:
            raise FieldValidationError(
                f"Field '{self.idd_field.name}' - Invalid choice: {value}. Valid choices are: {self.valid_choices}"
            )
        return v


class NodeField(AlphaField):
    """A node-name field — stored as a plain string."""

    pass


class ObjectListField(AlphaField):
    """A field that references another IdfObject by name — stored as a plain string."""

    pass


class ExternalListField(AlphaField):
    """A field that references an entry in an external list — stored as a plain string."""

    pass


class URLField(AlphaField):
    """A URL field — stored as a plain string."""

    pass


class HandleField(AlphaField):
    """A handle (UUID) field — stored as a plain string."""

    pass

from abc import ABC, abstractmethod
from enum import StrEnum

from energyplus_parser.constants import AUTOSIZE_VALUE, format_leading
from energyplus_parser.idd.idd_field import BoundTypes, IddField, IddFieldProperties, IddFieldType


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

    @property
    def required(self):
        return self.idd_field.properties.required

    @staticmethod
    def from_idd_field(idd_field) -> "IdfField":
        field_type = idd_field.type

        field: IdfField
        if field_type == IddFieldType.AlphaType:
            field = AlphaField(idd_field=idd_field)
        elif field_type == IddFieldType.IntegerType:
            field = IntegerField(idd_field=idd_field)
        elif field_type == IddFieldType.RealType:
            field = RealField(idd_field=idd_field)
        elif field_type == IddFieldType.ChoiceType:
            field = ChoiceField(idd_field=idd_field)
        elif field_type == IddFieldType.NodeType:
            raise NotImplementedError("NodeField not implemented yet")
        elif field_type == IddFieldType.ObjectListType:
            raise NotImplementedError("ObjectListField not implemented yet")
        elif field_type == IddFieldType.ExternalListType:
            raise NotImplementedError("ExternalListField not implemented yet")
        elif field_type == IddFieldType.URLType:
            raise NotImplementedError("URLField not implemented yet")
        elif field_type == IddFieldType.HandleType:
            raise NotImplementedError("HandleField not implemented yet")
        else:
            raise ValueError(f"Unknown field type: {field_type}")

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

    def text(self, is_last_field: bool = False) -> str:
        val = str(self.value(return_default=True)) or ""
        val = f"{format_leading(field_id=val, is_last_field=is_last_field)}!- {self.idd_field.name}"
        if self.idd_field.properties.units:
            val += f" {{{self.idd_field.properties.units}}}"
        return str(val)

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
        if not self.autocalculatable:
            raise FieldValidationError("Autocalculate not allowed")
        self._mode = NumericMode.AUTOCALCULATE
        self._value = None

    def autosize(self):
        if not self.autosizable:
            raise FieldValidationError("Autosize not allowed")
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

    def setInt(self, value: int) -> None:
        if not isinstance(value, (float, int)):
            raise TypeError("IntegerField value must be an int")
        v = int(value)
        self._validate_range(value=v)
        self._value = v
        self._mode = NumericMode.NORMAL

    @classmethod
    def _parse_number(cls, value: str) -> int:
        try:
            return int(value)
        except ValueError:
            raise FieldValidationError(f"Invalid integer: {value}")


class RealField(NumericField):
    def __init__(self, idd_field: IddField) -> None:
        super().__init__(idd_field=idd_field)
        self._value: float | None = None

    def setDouble(self, value: float) -> None:
        if not isinstance(value, (float, int)):
            raise TypeError("RealField value must be a float")
        v = float(value)
        self._validate_range(value=v)
        self._value = v
        self._mode = NumericMode.NORMAL

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
            raise FieldValidationError("This choice field is not a boolean field")
        self._value = "Yes" if value else "No"

    def validate(self):
        super().validate()
        if self._value is not None:
            self._canonical_validate_choice(value=self._value)

    def _canonical_validate_choice(self, value: str):
        v = self._canonical_map.get(value.lower(), None)
        if v is None:
            raise FieldValidationError(f"Invalid choice: {value}. Valid choices are: {self.valid_choices}")
        return v

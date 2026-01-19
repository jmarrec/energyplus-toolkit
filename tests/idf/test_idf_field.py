import pytest

from energyplus_parser.constants import BLOCK_INDENT
from energyplus_parser.idd.idd_field import BoundTypes, IddField, IddFieldProperties, IddFieldType, IddKey
from energyplus_parser.idf.idf_field import (
    AlphaField,
    ChoiceField,
    FieldValidationError,
    IdfField,
    IntegerField,
    NumericField,
    NumericMode,
    RealField,
)


def test_idf_autocalculated_field():
    objectName = "FakeObject"
    ori_text = r"""  N6 , \field Surface Layer Penetration Depth
       \type real
       \autocalculatable
       \units m
       \ip-units in
       \minimum> 0.0
       \default autocalculate"""

    idd_field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    field = RealField(idd_field=idd_field)
    assert field.is_defaulted()
    assert field.is_autocalculated()
    assert field.value(return_default=False) is None
    assert field.value(return_default=True) == NumericMode.AUTOCALCULATE

    field.autocalculate()
    assert not field.is_defaulted()
    assert field.is_autocalculated()
    assert field.value(return_default=False) == NumericMode.AUTOCALCULATE
    assert field.value(return_default=True) == NumericMode.AUTOCALCULATE

    field.setDouble(10.5)
    assert not field.is_defaulted()
    assert not field.is_autocalculated()
    assert field.value(return_default=False) == 10.5
    assert field.value(return_default=True) == 10.5

    with pytest.raises(FieldValidationError, match="-5.0 must be > 0.0"):
        field.setDouble(-5.0)


def test_idf_autosizable_field():
    objectName = "FakeObject"
    ori_text = r"""  N13; \field Cooling Coil Gross Rated Sensible Heat Ratio
       \note Rated sensible heat ratio (gross sensible capacity/gross total capacity)
       \note Sensible and total capacities do not include effect of supply fan heat
       \type real
       \autosizable
       \default autosize
       \minimum> 0.5
       \maximum 1.0"""

    idd_field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    field = RealField(idd_field=idd_field)
    assert field.is_defaulted()
    assert field.is_autosized()
    assert field.value(return_default=False) is None
    assert field.value(return_default=True) == NumericMode.AUTOSIZE

    field.autosize()
    assert not field.is_defaulted()
    assert field.is_autosized()
    assert field.value(return_default=False) == NumericMode.AUTOSIZE
    assert field.value(return_default=True) == NumericMode.AUTOSIZE

    field.setDouble(0.75)
    assert not field.is_defaulted()
    assert not field.is_autosized()
    assert field.value(return_default=False) == 0.75
    assert field.value(return_default=True) == 0.75

    with pytest.raises(FieldValidationError, match="1.5 must be <= 1.0"):
        field.setDouble(1.5)

    with pytest.raises(FieldValidationError, match="0.4 must be > 0.5"):
        field.setDouble(0.4)

    with pytest.raises(FieldValidationError, match="Autocalculate not allowed"):
        field.autocalculate()

import pytest

from energyplus_parser.idd.idd_field import BoundTypes, IddField
from energyplus_parser.idf.idf_field import ChoiceField, FieldValidationError, IntegerField, NumericMode, RealField
from tests.assertions import assert_has_method, refute_has_method


def test_idf_real_autocalculated_field():
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

    assert_has_method(field, "setString")

    assert_has_method(field, "setDouble")
    assert_has_method(field, "autocalculate")
    assert_has_method(field, "autosize")
    assert_has_method(field, "is_autosized")
    assert_has_method(field, "is_autocalculated")

    refute_has_method(field, "setInt")
    refute_has_method(field, "setBool")


def test_idf_real_autosizable_field():
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

    assert_has_method(field, "setString")

    assert_has_method(field, "setDouble")
    refute_has_method(field, "setInt")
    assert_has_method(field, "autocalculate")
    assert_has_method(field, "autosize")
    assert_has_method(field, "is_autosized")
    assert_has_method(field, "is_autocalculated")

    refute_has_method(field, "setBool")


def test_idf_integer_autosizable_field():
    objectName = "FakeObject"
    ori_text = r"""  N3 , \field Number of Beams
       \note Number of individual beam units in the zone
       \type integer
       \minimum> 0
       \autosizable
       \default autosize"""

    idd_field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    field = IntegerField(idd_field=idd_field)
    assert field.minimum_value == 0
    assert field.min_bound_type == BoundTypes.ExclusiveBound
    assert field.is_defaulted()
    assert field.is_autosized()
    assert field.value(return_default=False) is None
    assert field.value(return_default=True) == NumericMode.AUTOSIZE

    field.autosize()
    assert not field.is_defaulted()
    assert field.is_autosized()
    assert field.value(return_default=False) == NumericMode.AUTOSIZE
    assert field.value(return_default=True) == NumericMode.AUTOSIZE

    field.setInt(3)
    assert not field.is_defaulted()
    assert not field.is_autosized()
    assert field.value(return_default=False) == 3
    assert field.value(return_default=True) == 3

    with pytest.raises(FieldValidationError, match="1 must be > 0"):
        field.setInt(-1)

    with pytest.raises(FieldValidationError, match="Autocalculate not allowed"):
        field.autocalculate()

    assert_has_method(field, "setString")

    assert_has_method(field, "setInt")
    refute_has_method(field, "setDouble")
    assert_has_method(field, "autocalculate")
    assert_has_method(field, "autosize")
    assert_has_method(field, "is_autosized")
    assert_has_method(field, "is_autocalculated")

    refute_has_method(field, "setBool")


def test_idf_choice_field_boolean():
    objectName = "SimulationControl"
    ori_text = r"""  A1 , \field Do Zone Sizing Calculation
       \note If Yes, Zone sizing is accomplished from corresponding Sizing:Zone objects
       \note and autosize fields.
       \type choice
       \default No
       \key Yes
       \key No"""

    idd_field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    field = ChoiceField(idd_field=idd_field)

    assert field.is_boolean
    assert field.valid_choices == {"No", "Yes"}

    assert field.is_defaulted()
    assert field.value(return_default=False) is None
    assert field.value(return_default=True) == "No"

    field.setBool(value=False)
    assert not field.is_defaulted()
    assert field.value(return_default=False) == "No"
    assert field.value(return_default=True) == "No"

    field.setBool(value=True)
    assert not field.is_defaulted()
    assert field.value(return_default=False) == "Yes"
    assert field.value(return_default=True) == "Yes"

    field.setString("nO")
    assert not field.is_defaulted()
    assert field.value(return_default=False) == "No"
    assert field.value(return_default=True) == "No"

    assert_has_method(field, "setString")

    refute_has_method(field, "setDouble")
    refute_has_method(field, "setInt")
    refute_has_method(field, "autocalculate")
    refute_has_method(field, "autosize")
    refute_has_method(field, "is_autosized")
    refute_has_method(field, "is_autocalculated")

    assert_has_method(field, "setBool")

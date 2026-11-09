import logging

import pytest

from energyplus_toolkit.input.format_options import DEFAULT_FORMAT_OPTIONS
from energyplus_toolkit.input.idd.idd_field import (
    BoundTypes,
    FieldTypeChar,
    IddField,
    IddFieldParseError,
    IddFieldProperties,
    IddFieldType,
    IddKey,
)

BLOCK_INDENT = DEFAULT_FORMAT_OPTIONS.idd_tag_indent


def test_field_props_formatting():
    field_props = IddFieldProperties()
    field_props.required = True
    field_props.autosizable = True
    field_props.units = "m3/s"
    field_props.units = "gal/min"
    field_props.minBoundType = BoundTypes.InclusiveBound
    field_props.minBoundValue = 0.0
    field_props.maxBoundType = BoundTypes.ExclusiveBound
    field_props.maxBoundValue = 1.0
    expected = "\n".join(
        [
            f'{BLOCK_INDENT}\\required-field',
            f'{BLOCK_INDENT}\\autosizable',
            f'{BLOCK_INDENT}\\units gal/min',
            f'{BLOCK_INDENT}\\minimum 0.0',
            f'{BLOCK_INDENT}\\maximum< 1.0',
        ]
    )
    assert str(field_props) == expected


def test_idd_key_equality():
    assert IddKey(name="a") == IddKey(name="a")
    assert not (IddKey(name="a") != IddKey(name="a"))

    assert not (IddKey(name="a") == "a")
    assert IddKey(name="a") != "a"

    assert not (IddKey(name="a") == IddKey(name="b"))
    assert IddKey(name="a") != IddKey(name="b")


def test_parse_idd_choice_field():
    objectName = "SimulationControl"
    name = "Do Zone Sizing Calculation"
    ori_text = r"""  A1 , \field Do Zone Sizing Calculation
       \note If Yes, Zone sizing is accomplished from corresponding Sizing:Zone objects
       \note and autosize fields.
       \type choice
       \default No
       \key Yes
       \key No"""
    field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    assert field.name == name
    assert field.objectName == objectName
    assert field.keys == [IddKey(name="Yes"), IddKey(name="No")]
    assert not field.is_last_field

    field_props = field.properties
    assert field_props.type == IddFieldType.ChoiceType
    assert (
        field_props.note
        == "If Yes, Zone sizing is accomplished from corresponding Sizing:Zone objects\nand autosize fields."
    )
    assert not field_props.required
    assert not field_props.autosizable
    assert not field_props.autocalculatable
    assert not field_props.retaincase
    assert not field_props.deprecated
    assert not field_props.beginExtensible
    assert field_props.units is None
    assert field_props.ipUnits is None
    assert field_props.minBoundType == BoundTypes.Unbounded
    assert field_props.minBoundValue is None
    assert field_props.maxBoundType == BoundTypes.Unbounded
    assert field_props.maxBoundValue is None
    assert field_props.stringDefault == "No"
    assert field_props.numericDefault is None
    assert not field_props.objectLists
    assert not field_props.references
    assert not field_props.referenceClassNames
    assert not field_props.externalLists

    assert str(field) == ori_text


def test_parse_idd_autosizable_field():
    objectName = "FakeObject"
    name = "Cooling Coil Gross Rated Sensible Heat Ratio"
    ori_text = r"""  N13; \field Cooling Coil Gross Rated Sensible Heat Ratio
       \note Rated sensible heat ratio (gross sensible capacity/gross total capacity)
       \note Sensible and total capacities do not include effect of supply fan heat
       \type real
       \autosizable
       \minimum> 0.5
       \maximum 1.0"""

    field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys
    assert field.is_last_field

    field_props = field.properties
    assert field_props.type == IddFieldType.RealType
    assert (
        field_props.note == 'Rated sensible heat ratio (gross sensible capacity/gross total capacity)\n'
        'Sensible and total capacities do not include effect of supply fan heat'
    )
    assert not field_props.required
    assert field_props.autosizable
    assert not field_props.autocalculatable
    assert not field_props.retaincase
    assert not field_props.deprecated
    assert not field_props.beginExtensible
    assert field_props.units is None
    assert field_props.ipUnits is None
    assert field_props.minBoundType == BoundTypes.ExclusiveBound
    assert field_props.minBoundValue == 0.5
    assert field_props.maxBoundType == BoundTypes.InclusiveBound
    assert field_props.maxBoundValue == 1.0
    assert field_props.stringDefault is None
    assert field_props.numericDefault is None
    assert not field_props.objectLists
    assert not field_props.references
    assert not field_props.referenceClassNames
    assert not field_props.externalLists

    assert str(field) == ori_text


def test_parse_idd_extensible_field():
    objectName = "DesignSpecification:OutdoorAir:SpaceList"
    name = "Space 1 Name"
    ori_text = r"""  A2 , \field Space 1 Name
       \begin-extensible
       \type object-list
       \object-list SpaceNames"""
    field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    assert field.field_id == "A2"

    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys
    assert not field.is_last_field

    field_props = field.properties
    assert field_props.type == IddFieldType.ObjectListType
    assert not field_props.note
    assert not field_props.required
    assert not field_props.autosizable
    assert not field_props.autocalculatable
    assert not field_props.retaincase
    assert not field_props.deprecated
    assert field_props.beginExtensible
    assert field_props.units is None
    assert field_props.ipUnits is None
    assert field_props.minBoundType == BoundTypes.Unbounded
    assert field_props.minBoundValue is None
    assert field_props.maxBoundType == BoundTypes.Unbounded
    assert field_props.maxBoundValue is None
    assert field_props.stringDefault is None
    assert field_props.numericDefault is None
    assert field_props.objectLists == ['SpaceNames']
    assert not field_props.references
    assert not field_props.referenceClassNames
    assert not field_props.externalLists

    assert str(field) == ori_text


def test_parse_idd_field_with_reference():
    objectName = "ZoneHVAC:TerminalUnit:VariableRefrigerantFlow"
    name = "Zone Terminal Unit Name"
    ori_text = r"""  A1 , \field Zone Terminal Unit Name
       \type alpha
       \reference ZoneTerminalUnitNames
       \reference DOAToZonalUnit
       \reference ZoneEquipmentNames
       \reference validBranchEquipmentNames
       \reference validOASysEquipmentNames
       \reference-class-name validBranchEquipmentTypes
       \reference-class-name validOASysEquipmentTypes"""

    field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    assert field.field_id == "A1"
    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys
    assert not field.is_last_field

    field_props = field.properties
    assert field_props.type == IddFieldType.AlphaType
    assert not field_props.note
    assert not field_props.required
    assert not field_props.autosizable
    assert not field_props.autocalculatable
    assert not field_props.retaincase
    assert not field_props.deprecated
    assert not field_props.beginExtensible
    assert field_props.units is None
    assert field_props.ipUnits is None
    assert field_props.minBoundType == BoundTypes.Unbounded
    assert field_props.minBoundValue is None
    assert field_props.maxBoundType == BoundTypes.Unbounded
    assert field_props.maxBoundValue is None
    assert field_props.stringDefault is None
    assert field_props.numericDefault is None
    assert not field_props.objectLists
    assert field_props.references == [
        "ZoneTerminalUnitNames",
        "DOAToZonalUnit",
        "ZoneEquipmentNames",
        "validBranchEquipmentNames",
        "validOASysEquipmentNames",
    ]
    assert field_props.referenceClassNames == ["validBranchEquipmentTypes", "validOASysEquipmentTypes"]
    assert not field_props.externalLists

    assert str(field) == ori_text


def test_parse_idd_numeric_default():
    objectName = "Material:RoofVegetation"
    name = "Thickness"
    ori_text = r"""  N6 ; \field Thickness
       \type real
       \units m
       \ip-units in
       \minimum> 0.05
       \maximum 0.7
       \default 0.1"""

    field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    assert field.field_id == "N6"
    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys
    assert field.is_last_field

    field_props = field.properties
    assert field_props.type == IddFieldType.RealType
    assert not field_props.note
    assert not field_props.required
    assert not field_props.autosizable
    assert not field_props.autocalculatable
    assert not field_props.retaincase
    assert not field_props.deprecated
    assert not field_props.beginExtensible
    assert field_props.units == "m"
    assert field_props.ipUnits == "in"
    assert field_props.minBoundType == BoundTypes.ExclusiveBound
    assert field_props.minBoundValue == 0.05
    assert field_props.maxBoundType == BoundTypes.InclusiveBound
    assert field_props.maxBoundValue == 0.7
    assert field_props.stringDefault == "0.1"
    assert field_props.numericDefault == 0.1
    assert not field_props.objectLists
    assert not field_props.references
    assert not field_props.referenceClassNames
    assert not field_props.externalLists

    assert str(field) == ori_text


@pytest.mark.parametrize(
    "min_text, max_text",
    [
        (">0.0", "<1.0"),
        ("> 0.0", "< 1.0"),
        (" >0", " <1"),
        (" > 0.0", " < 1.0"),
    ],
    ids=["no-space", "space-after", "space-before", "space-both"],
)
def test_parse_idd_exclusive_bounds_spacing(min_text, max_text):
    # Older EnergyPlus IDDs sometimes put a space between the tag and the operator, eg '\minimum >0' (V25-1-0 and
    # earlier) or '\minimum > 0.0' (V8-1-0, V8-2-0)
    objectName = "FakeObject"
    ori_text = "\n".join(
        [
            r"  N1 ; \field Some Value",
            r"       \type real",
            rf"       \minimum{min_text}",
            rf"       \maximum{max_text}",
        ]
    )

    field = IddField.load(objectName=objectName, field_lines=ori_text.splitlines())

    field_props = field.properties
    assert field_props.minBoundType == BoundTypes.ExclusiveBound
    assert field_props.minBoundValue == 0.0
    assert field_props.maxBoundType == BoundTypes.ExclusiveBound
    assert field_props.maxBoundValue == 1.0

    # Output is normalized to the current IDD convention
    assert str(field) == "\n".join(
        [
            r"  N1 ; \field Some Value",
            r"       \type real",
            r"       \minimum> 0.0",
            r"       \maximum< 1.0",
        ]
    )


def test_is_name_field_with_references():
    """A field with \\reference tags (and no \\object-list) is a name field."""
    field = IddField.load(
        objectName="Zone",
        field_lines=r"""  A1 , \field Name
       \type alpha
       \reference Zones
       \reference ZoneNames""".splitlines(),
    )
    assert field.is_name_field()


def test_is_name_field_literal_name_alpha():
    """A field literally named 'Name' with alpha type is a name field."""
    field = IddField.load(
        objectName="SomeObject",
        field_lines=r"""  A1 , \field Name
       \type alpha""".splitlines(),
    )
    assert field.is_name_field()


def test_is_name_field_with_object_list_not_name():
    """A field with both \\reference and \\object-list is NOT a name field."""
    field = IddField.load(
        objectName="SomeObject",
        field_lines=r"""  A1 , \field Component Name
       \type object-list
       \object-list validBranchEquipmentNames
       \reference SomeRef""".splitlines(),
    )
    assert not field.is_name_field()


def test_is_name_field_plain_alpha_not_name():
    """A plain alpha field that isn't named 'Name' and has no references is not a name field."""
    field = IddField.load(
        objectName="SomeObject",
        field_lines=r"""  A1 , \field Description
       \type alpha""".splitlines(),
    )
    assert not field.is_name_field()


def test_parse_idd_required_field():
    """\\required-field must be read, and written back (it was set on the field instead of its properties)."""
    ori_text = r"""  A1 , \field Zone Terminal Unit Name
       \required-field
       \type alpha
       \reference ZoneTerminalUnitNames"""
    field = IddField.load(objectName="ZoneHVAC:TerminalUnit:VariableRefrigerantFlow", field_lines=ori_text.splitlines())
    assert field.properties.required
    # Written back in the formatter's property order (\type first)
    assert str(field) == "\n".join(
        [
            r"  A1 , \field Zone Terminal Unit Name",
            r"       \type alpha",
            r"       \required-field",
            r"       \reference ZoneTerminalUnitNames",
        ]
    )


@pytest.mark.parametrize("second_name", ["Name", "Other Name"])
def test_parse_idd_duplicate_field_line(second_name):
    """A field has one \\field line, on its first line: a second one is malformed, even with the same name."""
    with pytest.raises(IddFieldParseError, match="Duplicate"):
        IddField.load(
            objectName="Zone",
            field_lines=["  A1 , \\field Name", "       \\type alpha", f"       \\field {second_name}"],
        )


@pytest.mark.parametrize(
    "field_lines, exception, message",
    [
        (["  A1 , \\field Name", "       \\type alpha", "       \\field Other"], IddFieldParseError, "Duplicate"),
        (["  A1 , \\field Name", "       \\type choice", "       \\key"], ValueError, "Key name is empty"),
        (["  A1 , \\field Name", "       \\bogus"], ValueError, "Unknown field property text 'bogus'"),
        (["  A1 , \\field Name", "       \\type alpha", "junk", "more junk"], IddFieldParseError, "Unexpected content"),
        (
            ["  N1 , \\field Name", "       \\type real", "       \\default abc"],
            ValueError,
            r"Invalid \\default value 'abc'",
        ),
        (["  N1 , \\field Name", "       \\minimum> abc"], ValueError, r"Invalid \\minimum value 'abc'"),
        (["  N1 , \\field Name", "       \\maximum< abc"], ValueError, r"Invalid \\maximum value 'abc'"),
    ],
)
def test_parse_error_says_where(field_lines, exception, message):
    with pytest.raises(exception, match=f"^In 'Some:Object', field 'Name': {message}"):
        IddField.load(objectName="Some:Object", field_lines=field_lines)


@pytest.mark.parametrize(
    "field_lines, exception, message",
    [
        ([], ValueError, "No lines provided"),
        (["  A1 , no field here"], IddFieldParseError, "First line of field does not contain"),
    ],
)
def test_parse_error_before_field_name_is_known(field_lines, exception, message):
    with pytest.raises(exception, match=f"^In 'Some:Object': {message}"):
        IddField.load(objectName="Some:Object", field_lines=field_lines)


@pytest.mark.parametrize("junk", ["oops this is junk", "units m"])
@pytest.mark.parametrize("after_junk", [[], ["       \\units m"], ["       \\units m", "       \\minimum 0"]])
def test_parse_single_junk_line_after_properties(junk, after_junk):
    """The first line that isn't a property must be checked too, eg "units m" is a \\units missing its backslash.
    The error is about that line, even if valid properties follow it."""
    field_lines = ["  N1 , \\field Height", "       \\type real", junk, *after_junk]
    with pytest.raises(IddFieldParseError, match=f"Unexpected content found after field properties: '{junk}'"):
        IddField.load(objectName="Some:Object", field_lines=field_lines)


@pytest.mark.parametrize(
    "tag", ["autosizable", "autocalculatable", "begin-extensible", "deprecated", "required-field", "retaincase"]
)
@pytest.mark.parametrize("rest", [" BLABLABLA", "s", " ! a comment"])
def test_parse_valueless_flag_with_a_value_is_an_error(tag, rest):
    """The text after it would be lost. "s" is a typo: \\autosizables."""
    field_lines = ["  N1 , \\field Name", "       \\type real", f"       \\{tag}{rest}"]
    with pytest.raises(ValueError, match=f"^In 'Some:Object', field 'Name': \\\\{tag} takes no value"):
        IddField.load(objectName="Some:Object", field_lines=field_lines)


@pytest.mark.parametrize(
    "tag",
    [
        "default",
        "external-list",
        "ip-units",
        "key",
        "maximum",
        "minimum",
        "object-list",
        "reference",
        "reference-class-name",
        "type",
        "units",
        "unitsBasedOnField",
    ],
)
@pytest.mark.parametrize("field_id, field_type", [("A1", "alpha"), ("N1", "real")])
def test_parse_stray_property_is_an_error(tag, field_id, field_type):
    """A property that takes a value, left alone on its line."""
    field_lines = [f"  {field_id} , \\field Name", f"       \\type {field_type}", f"       \\{tag}"]
    with pytest.raises((ValueError, IddFieldParseError), match="^In 'Some:Object', field 'Name': "):
        IddField.load(objectName="Some:Object", field_lines=field_lines)


@pytest.mark.parametrize(
    "tag", ["autosizable", "autocalculatable", "begin-extensible", "deprecated", "required-field", "retaincase"]
)
def test_parse_property_without_value_is_not_stray(tag):
    IddField.load(
        objectName="Some:Object", field_lines=["  N1 , \\field Name", "       \\type real", f"       \\{tag}"]
    )


@pytest.mark.parametrize("tag", ["note", "memo"])
def test_empty_note_is_discarded(caplog, tag):
    """Like an empty \\memo in IddObject: dropped, with an info message."""
    field_lines = ["  A1 , \\field Name", "       \\note First", f"       \\{tag}", "       \\note Second"]
    with caplog.at_level(logging.INFO, logger="IddField"):
        field = IddField.load(objectName="Some:Object", field_lines=field_lines)
    assert field.properties.note == "First\nSecond"
    assert f"In 'Some:Object', field 'Name': \\{tag} line is empty" in caplog.text


def test_note_keeps_its_exclamation_mark():
    field_lines = ["  A1 , \\field Name", "       \\note Careful! not a comment"]
    assert IddField.load(objectName="Some:Object", field_lines=field_lines).properties.note == "Careful! not a comment"


def test_memo_warning_says_where(caplog):
    with caplog.at_level(logging.WARNING, logger="IddField"):
        field = IddField.load(objectName="Some:Object", field_lines=["  A1 , \\field Name", "       \\memo Some text"])

    assert field.properties.note == "Some text"
    assert "In 'Some:Object', field 'Name': Memo property is deprecated; use Note property instead." in caplog.messages


@pytest.mark.parametrize(
    "idd_name, name, group_0_name, group_2_name",
    [
        ("Vertex 1 X-coordinate", "Vertex X-coordinate", "Vertex 1 X-coordinate", "Vertex 3 X-coordinate"),
        ("DayType List 1", "DayType List", "DayType List 1", "DayType List 3"),
        # The group number is the last one: OpenStudio makes the DX coil speeds extensible
        (
            "2017 Speed 1 Rated Evaporator Fan Power Per Volume Flow Rate",
            "2017 Speed Rated Evaporator Fan Power Per Volume Flow Rate",
            "2017 Speed 1 Rated Evaporator Fan Power Per Volume Flow Rate",
            "2017 Speed 3 Rated Evaporator Fan Power Per Volume Flow Rate",
        ),
        ("1 Speed Rated Flow", "Speed Rated Flow", "1 Speed Rated Flow", "3 Speed Rated Flow"),
        # Site:SpectrumData: no number, it's appended, like OpenStudio does
        ("Wavelength", "Wavelength", "Wavelength 1", "Wavelength 3"),
    ],
)
def test_extensible_field_name_for_group(idd_name, name, group_0_name, group_2_name):
    field = IddField.load(objectName="Some:Object", field_lines=[f"  N1 , \\field {idd_name}", "       \\type real"])
    field.markExtensible()
    assert field.extensible
    assert field.name == name
    assert field.name_for_group(0) == group_0_name
    assert field.name_for_group(2) == group_2_name
    assert repr(field).startswith(f"  N1 , \\field {idd_name}\n")  # written back to the IDD as it was


def test_mark_extensible_twice_is_an_error():
    field = IddField.load(objectName="Some:Object", field_lines=["  N1 , \\field Vertex 1 X-coordinate"])
    field.markExtensible()
    with pytest.raises(ValueError, match="already marked extensible"):
        field.markExtensible()


def test_regular_field_name_for_group_is_its_name():
    field = IddField.load(
        objectName="Some:Object", field_lines=["  N1 , \\field Speed 1 Rated Flow", "       \\type real"]
    )
    assert not field.extensible
    assert field.name == "Speed 1 Rated Flow"
    assert field.name_for_group(2) == "Speed 1 Rated Flow"


def test_parse_idd_units_based_on_field():
    """\\unitsBasedOnField was read as \\units "BasedOnField A2" (a case-sensitive check on lowercased text): the IDD
    was written back with "\\units BasedOnField A2", and IDF comments with "{BasedOnField A2}"."""
    ori_text = r"""  N7 , \field Minimum Value of x
       \type real
       \required-field
       \unitsBasedOnField A2"""
    field = IddField.load(objectName="Curve:Biquadratic", field_lines=ori_text.splitlines())
    assert field.properties.unitsBasedOnField == "A2"
    assert field.properties.units is None
    assert str(field) == ori_text


@pytest.mark.parametrize(
    "field_id, field_type, expected",
    [
        ("A1", "alpha", FieldTypeChar.Alpha),
        ("A12", "choice", FieldTypeChar.Alpha),
        ("N1", "real", FieldTypeChar.Numeric),
        ("N12", "choice", FieldTypeChar.Numeric),  # eg WindowMaterial:Screen: the type doesn't say it
    ],
)
def test_field_type_char(field_id, field_type, expected):
    field_lines = [f"  {field_id} , \\field Name", f"       \\type {field_type}", "       \\key Yes"]
    field = IddField.load(objectName="Some:Object", field_lines=field_lines)
    assert field.field_type_char == expected


def test_alpha_field_with_keys_and_no_type_is_a_choice(caplog):
    """Output:Table:ReportPeriod "Report Name" (V22-2-0 to V25-1-0): it has \\key lines, but no \\type choice."""
    with caplog.at_level(logging.WARNING, logger="IddField"):
        field = IddField.load(objectName="Some:Object", field_lines=["  A1 , \\field Name", "       \\key Yes"])
    assert field.properties.type == IddFieldType.ChoiceType
    assert "\\type choice" in str(field)
    assert "In 'Some:Object', field 'Name': Field has keys but no \\type: assuming choice" in caplog.text


@pytest.mark.parametrize("field_type", ["alpha", "node"])
def test_explicit_type_with_keys_is_kept(caplog, field_type):
    field_lines = ["  A1 , \\field Name", f"       \\type {field_type}", "       \\key Yes"]
    with caplog.at_level(logging.ERROR, logger="IddField"):
        field = IddField.load(objectName="Some:Object", field_lines=field_lines)
    assert field.properties.type == IddFieldType(field_type)
    assert "Field is not of type choice but has non-empty keys" in caplog.text

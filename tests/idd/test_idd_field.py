from energyplus_parser.constants import BLOCK_INDENT
from energyplus_parser.idd.idd_field import BoundTypes, IddField, IddFieldProperties, IddFieldType, IddKey


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
    text = "".join([x.strip() for x in ori_text.splitlines()])

    field = IddField.load(name=name, text=text, objectName=objectName)

    assert field.name == name
    assert field.objectName == objectName
    assert field.keys == [IddKey(name="Yes"), IddKey(name="No")]

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

    text = "".join([x.strip() for x in ori_text.splitlines()])

    field = IddField.load(name=name, text=text, objectName=objectName)
    field.is_last_field = True

    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys

    field_props = field.properties
    assert field_props.type == IddFieldType.RealType
    assert (
        field_props.note
        == 'Rated sensible heat ratio (gross sensible capacity/gross total capacity)\nSensible and total capacities do not include effect of supply fan heat'
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
       \type object-list
       \begin-extensible
       \object-list SpaceNames"""
    text = "".join([x.strip() for x in ori_text.splitlines()])

    field = IddField.load(name=name, text=text, objectName=objectName)

    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys

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
    text = "".join([x.strip() for x in ori_text.splitlines()])

    field = IddField.load(name=name, text=text, objectName=objectName)

    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys

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
    ori_text = r"""  N6 , \field Thickness
       \type real
       \units m
       \ip-units in
       \minimum> 0.05
       \maximum 0.7
       \default 0.1"""
    text = "".join([x.strip() for x in ori_text.splitlines()])

    field = IddField.load(name=name, text=text, objectName=objectName)

    assert field.name == name
    assert field.objectName == objectName
    assert not field.keys

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

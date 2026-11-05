import pytest

from energyplus_toolkit.input.idd.idd_object import IddObject
from energyplus_toolkit.input.idf import idf_constants
from energyplus_toolkit.input.idf.idf_field import FieldValidationError, NumericMode
from energyplus_toolkit.input.idf.idf_object import IdfObject, IdfObjectError

# ---------------------------------------------------------------------------
# Helpers: build IddObjects from inline IDD text
# ---------------------------------------------------------------------------

SIMULATION_CONTROL_IDD = """\
SimulationControl,
       \\unique-object
       \\min-fields 5
  A1 , \\field Do Zone Sizing Calculation
       \\note If Yes, Zone sizing is accomplished from corresponding Sizing:Zone objects
       \\type choice
       \\default No
       \\key Yes
       \\key No
  A2 , \\field Do System Sizing Calculation
       \\type choice
       \\default No
       \\key Yes
       \\key No
  A3 , \\field Do Plant Sizing Calculation
       \\type choice
       \\default No
       \\key Yes
       \\key No
  A4 , \\field Run Simulation for Sizing Periods
       \\type choice
       \\default Yes
       \\key Yes
       \\key No
  A5 ; \\field Run Simulation for Weather File Run Periods
       \\type choice
       \\default Yes
       \\key Yes
       \\key No
"""

ZONE_IDD = """\
Zone,
       \\min-fields 1
  A1 , \\field Name
       \\type alpha
       \\required-field
       \\reference ZoneNames
  N1 , \\field Direction of Relative North
       \\units deg
       \\type real
       \\default 0
  N2 , \\field X Origin
       \\units m
       \\type real
       \\default 0
  N3 , \\field Y Origin
       \\units m
       \\type real
       \\default 0
  N4 ; \\field Z Origin
       \\units m
       \\type real
       \\default 0
"""

BRANCH_IDD = """\
Branch,
       \\extensible:4
       \\memo List components on the branch in simulation and connection order
       \\memo Note: this should NOT include splitters or mixers which define
       \\memo endpoints of branches
  A1,  \\field Name
       \\required-field
       \\reference Branches
  A2,  \\field Pressure Drop Curve Name
       \\type object-list
       \\object-list UnivariateFunctions
       \\note Optional field to include this branch in plant pressure drop calculations
  A3,  \\field Component 1 Object Type
       \\begin-extensible
       \\required-field
       \\type object-list
       \\object-list validBranchEquipmentTypes
  A4,  \\field Component 1 Name
       \\required-field
       \\type object-list
       \\object-list validBranchEquipmentNames
  A5,  \\field Component 1 Inlet Node Name
       \\required-field
       \\type node
  A6,  \\field Component 1 Outlet Node Name
       \\required-field
       \\type node
  A7,  \\field Component 2 Object Type
       \\type object-list
       \\object-list validBranchEquipmentTypes
  A8,  \\field Component 2 Name
       \\type object-list
       \\object-list validBranchEquipmentNames
  A9,  \\field Component 2 Inlet Node Name
       \\type node
  A10; \\field Component 2 Outlet Node Name
       \\type node
"""


def make_idd_object(idd_text: str, group: str = "TestGroup") -> IddObject:
    return IddObject.load(group=group, object_lines=idd_text.splitlines())


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------


def test_idf_object_init_from_idd():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    obj = IdfObject(idd_object=idd_obj)

    assert obj.idd_object is idd_obj
    assert obj.comment == ""
    assert obj.num_fields() == 5
    assert obj.num_extensible_groups() == 0


def test_idf_object_default_values():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    obj = IdfObject(idd_object=idd_obj)

    # All fields are defaulted; getString with return_default=True gives defaults
    assert obj.getString(0, return_default=True) == "No"
    assert obj.getString(1, return_default=True) == "No"
    assert obj.getString(3, return_default=True) == "Yes"
    assert obj.getString(4, return_default=True) == "Yes"

    # Without return_default, unset fields return None
    assert obj.getString(0, return_default=False) is None


def test_idf_object_name_from_first_field():
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "ZONE ONE")
    assert obj.name == "ZONE ONE"


def test_idf_object_name_field_index():
    assert make_idd_object(ZONE_IDD).name_field_index() == 0
    assert make_idd_object(SIMULATION_CONTROL_IDD).name_field_index() is None


def test_idf_object_name_and_name_string():
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)

    assert obj.name is None
    assert obj.nameString() == ""

    obj.setName("My Zone")
    assert obj.name == "My Zone"
    assert obj.nameString() == "My Zone"


def test_idf_object_set_name_no_name_field_raises():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    obj = IdfObject(idd_object=idd_obj)
    with pytest.raises(IdfObjectError):
        obj.setName("ShouldFail")


# ---------------------------------------------------------------------------
# get_value — native-type accessor
# ---------------------------------------------------------------------------


def test_idf_object_get_value_types():
    """get_value returns the native Python type for each field class."""
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "MyZone")  # AlphaField  → str
    obj.setDouble(1, 45.0)  # RealField   → float
    obj.setDouble(2, 1.0)  # RealField   → float

    assert obj.get_value(0) == "MyZone"
    assert isinstance(obj.get_value(0), str)

    assert obj.get_value(1) == 45.0
    assert isinstance(obj.get_value(1), float)

    # Unset field returns None without return_default
    assert obj.get_value(3) is None
    # With return_default returns the IDD default (0.0 for Y Origin)
    assert obj.get_value(3, return_default=True) == 0.0


def test_idf_object_get_value_integer():
    """get_value returns int for IntegerField."""
    idd_obj = make_idd_object(SIMULATION_CONTROL_7_FIELDS_IDD)
    idf_text = """
SimulationControl,
  No, No, No, Yes, Yes, No,
  3;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj.get_value(6) == 3
    assert isinstance(obj.get_value(6), int)


def test_idf_object_get_value_autosize():
    """get_value returns NumericMode.AUTOSIZE for an autosized field."""
    autosize_idd = """\
Coil:Heating:Fuel,
  A1, \\field Name
  N1; \\field Nominal Capacity
      \\type real
      \\autosizable
      \\default autosize
      \\units W
"""
    idd_obj = make_idd_object(autosize_idd)
    obj = IdfObject(idd_object=idd_obj)

    # Default is autosize; return_default exposes NumericMode
    assert obj.get_value(1, return_default=True) == NumericMode.AUTOSIZE

    # Parsing "autosize" from text also yields NumericMode
    obj2 = IdfObject.load(idd_object=idd_obj, text="Coil:Heating:Fuel,\n  MyCoil,\n  autosize;\n")
    assert obj2.get_value(1) == NumericMode.AUTOSIZE


def test_idf_object_set_get_string():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    obj = IdfObject(idd_object=idd_obj)

    obj.setString(0, "Yes")
    assert obj.getString(0) == "Yes"

    obj.setString(1, "No")
    assert obj.getString(1) == "No"


def test_idf_object_set_string_invalid_choice():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    obj = IdfObject(idd_object=idd_obj)
    with pytest.raises(FieldValidationError):
        obj.setString(0, "Maybe")


def test_idf_object_index_out_of_range():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    obj = IdfObject(idd_object=idd_obj)
    with pytest.raises(IndexError):
        obj.getString(99)


# ---------------------------------------------------------------------------
# setDouble / getDouble
# ---------------------------------------------------------------------------


def test_idf_object_set_get_double():
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)

    obj.setString(0, "TestZone")
    obj.setDouble(1, 45.0)  # Direction of Relative North
    assert obj.getDouble(1) == 45.0


def test_idf_object_get_double_default():
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)
    # Default for N1..N4 is 0.0
    assert obj.getDouble(1, return_default=True) == 0.0
    assert obj.getDouble(1, return_default=False) is None


def test_idf_object_set_double_wrong_type():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)  # all ChoiceFields
    obj = IdfObject(idd_object=idd_obj)
    with pytest.raises(TypeError):
        obj.setDouble(0, 1.0)


# ---------------------------------------------------------------------------
# setInt / getInt
# ---------------------------------------------------------------------------


SCHEDULE_TYPE_LIMITS_IDD = """\
ScheduleTypeLimits,
  A1 , \\field Name
       \\type alpha
       \\required-field
  N1 , \\field Lower Limit Value
       \\type real
  N2 , \\field Upper Limit Value
       \\type real
  A2 , \\field Numeric Type
       \\type choice
       \\key Continuous
       \\key Discrete
  A3 ; \\field Unit Type
       \\type choice
       \\default Dimensionless
       \\key Dimensionless
       \\key Temperature
       \\key DeltaTemperature
       \\key PrecipitationRate
       \\key Angle
       \\key ConvectionCoefficient
       \\key ActivityLevel
       \\key Velocity
       \\key Capacity
       \\key Power
       \\key Availability
       \\key Percent
       \\key Control
       \\key Mode
       \\key MassFlowRate
       \\key VolumetricFlowRate
"""

NUM_OF_TIMESTEPS_IDD = """\
Timestep,
  N1 ; \\field Number of Timesteps per Hour
       \\type integer
       \\minimum 1
       \\maximum 60
       \\default 6
"""


def test_idf_object_set_get_int():
    idd_obj = make_idd_object(NUM_OF_TIMESTEPS_IDD)
    obj = IdfObject(idd_object=idd_obj)

    obj.setInt(0, 4)
    assert obj.getInt(0) == 4


def test_idf_object_get_int_default():
    idd_obj = make_idd_object(NUM_OF_TIMESTEPS_IDD)
    obj = IdfObject(idd_object=idd_obj)
    assert obj.getInt(0, return_default=True) == 6
    assert obj.getInt(0, return_default=False) is None


def test_idf_object_set_int_wrong_type():
    idd_obj = make_idd_object(ZONE_IDD)  # N fields are RealField
    obj = IdfObject(idd_object=idd_obj)
    with pytest.raises(TypeError):
        obj.setInt(1, 1)


# ---------------------------------------------------------------------------
# singleLine format: zero values must be kept (0 is falsy, but it's not an empty field)
# ---------------------------------------------------------------------------

SCHEDULE_CONSTANT_IDD = """\
Schedule:Constant,
   \\memo Constant hourly value for entire year.
   \\format singleLine
  A1 , \\field Name
       \\required-field
       \\type alpha
       \\reference ScheduleNames
  A2 , \\field Schedule Type Limits Name
       \\type object-list
       \\object-list ScheduleTypeLimitsNames
  N1 ; \\field Hourly Value
       \\type real
       \\default 0
"""

# Shortened to 3 months
GROUND_TEMPERATURE_IDD = """\
Site:GroundTemperature:BuildingSurface,
       \\unique-object
       \\format singleLine
  N1 , \\field January Ground Temperature
       \\units C
       \\type real
       \\default 18
  N2 , \\field February Ground Temperature
       \\units C
       \\type real
       \\default 18
  N3 ; \\field March Ground Temperature
       \\units C
       \\type real
       \\default 18
"""


@pytest.mark.parametrize("value", ["0", "0.0"])
def test_idf_object_single_line_keeps_trailing_zero(value):
    idd_obj = make_idd_object(SCHEDULE_CONSTANT_IDD)
    obj = IdfObject.load(idd_object=idd_obj, text=f"Schedule:Constant,Always Off,,{value};")
    assert str(obj).strip() == "Schedule:Constant,Always Off,,0.0;"


def test_idf_object_single_line_keeps_zero_in_the_middle():
    """A zero that isn't the default (18 here) must not become an empty field, which would mean 18."""
    idd_obj = make_idd_object(GROUND_TEMPERATURE_IDD)
    obj = IdfObject.load(idd_object=idd_obj, text="Site:GroundTemperature:BuildingSurface,0,0,19.5;")
    assert str(obj).strip() == "Site:GroundTemperature:BuildingSurface,0.0,0.0,19.5;"


def test_idf_object_single_line_keeps_integer_reals(monkeypatch):
    monkeypatch.setattr(idf_constants, "IDF_KEEP_INTEGER_REALS", True)
    idd_obj = make_idd_object(GROUND_TEMPERATURE_IDD)
    obj = IdfObject.load(idd_object=idd_obj, text="Site:GroundTemperature:BuildingSurface,0,18.0,19.5;")
    assert str(obj).strip() == "Site:GroundTemperature:BuildingSurface,0,18.0,19.5;"


def test_idf_object_single_line_still_trims_trailing_empty_fields():
    idd_obj = make_idd_object(SCHEDULE_CONSTANT_IDD)
    obj = IdfObject.load(idd_object=idd_obj, text="Schedule:Constant,Always Off,,;")
    assert str(obj).strip() == "Schedule:Constant,Always Off;"


# ---------------------------------------------------------------------------
# Parsing from IDF text
# ---------------------------------------------------------------------------


def test_idf_object_load_simulation_control():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    idf_text = """
SimulationControl,
  Yes,                     !- Do Zone Sizing Calculation
  Yes,                     !- Do System Sizing Calculation
  No,                      !- Do Plant Sizing Calculation
  No,                      !- Run Simulation for Sizing Periods
  Yes;                     !- Run Simulation for Weather File Run Periods
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)

    assert obj.getString(0) == "Yes"
    assert obj.getString(1) == "Yes"
    assert obj.getString(2) == "No"
    assert obj.getString(3) == "No"
    assert obj.getString(4) == "Yes"


def test_idf_object_load_preserves_comment():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    idf_text = """
! This is a simulation control block
SimulationControl,
  No;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert "This is a simulation control block" in obj.comment


def test_idf_object_load_empty_fields():
    """Empty fields (two consecutive commas) should leave the field at default."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = """
Zone,
  MyZone,
  ,
  ,
  ,
  0;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj.name == "MyZone"
    # X,Y origin remain defaulted (0.0)
    assert obj.getDouble(2, return_default=True) == 0.0
    assert obj.getDouble(4) == 0.0


def test_idf_object_load_wrong_type_raises():
    idd_obj = make_idd_object(ZONE_IDD)
    with pytest.raises(IdfObjectError):
        IdfObject.load(idd_object=idd_obj, text="SimulationControl,\n  Yes;")


# ---------------------------------------------------------------------------
# Field comments  (OpenStudio parity: IdfObject::fieldComment)
#
# Rule: only bare "!" comments (not "!-") are stored as user field comments.
# The standard "!- field name" IDD annotation is treated as absent (None).
# ---------------------------------------------------------------------------


def test_idf_object_load_field_comment_stored():
    """A bare ! comment (not !-) after a field value is stored as that field's comment."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = """\
Zone,
  ZoneB, ! This is a field comment for the Name field
  20.0;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj.name == "ZoneB"
    assert obj._fields[0].comment is not None
    assert "field comment for the Name field" in obj._fields[0].comment


def test_idf_object_load_field_comment_absent_for_idd_annotation():
    """The standard !- field-name annotation is NOT stored as a field comment."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = """\
Zone,
  ZoneA,                   !- Name
  90.0;                    !- Direction of Relative North {deg}
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj._fields[0].comment is None
    assert obj._fields[1].comment is None


def test_idf_object_load_field_comment_absent_returns_none():
    """A field with no inline comment at all returns None from fieldComment()."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = """\
Zone,
  ZoneA,
  10.0;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj._fields[0].comment is None
    assert obj._fields[1].comment is None


def test_idf_object_load_pre_field_comment_is_object_comment():
    """A ! comment appearing inside the object block before any field value is part of the object comment."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = """\
Zone,
  ! A comment placed before the fields is understood as an object comment
  ZoneB, ! This is a field comment for the Name field
  20.0;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj.name == "ZoneB"
    assert "comment placed before the fields" in obj.comment
    assert obj._fields[0].comment is not None
    assert "field comment for the Name field" in obj._fields[0].comment


def test_idf_object_load_preceding_and_pre_field_comment_combined():
    """A preceding comment and an in-object pre-field comment are both part of the object comment."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = """\
! This is an object comment
Zone,
  ! And this is appended to the object comment
  ZoneB, ! This is a field comment for the Name field
  20.0;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj.name == "ZoneB"
    assert "This is an object comment" in obj.comment
    assert "And this is appended to the object comment" in obj.comment
    assert obj._fields[0].comment is not None
    assert "field comment for the Name field" in obj._fields[0].comment


def test_idf_object_load_inline_object_type_comment_is_object_comment():
    """A bare ! comment on the same line as the object type is part of the object comment."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = """\
Zone, ! This is also understood as an object comment
  ZoneC,
  30.0;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)
    assert obj.name == "ZoneC"
    assert "also understood as an object comment" in obj.comment


# ---------------------------------------------------------------------------
# Extensible groups
# ---------------------------------------------------------------------------


def test_idf_object_push_extensible_group():
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)

    assert not obj.idd_object.properties.extensible or obj.num_extensible_groups() == 0

    group = obj.push_extensible_group(["Coil:Heating:Fuel", "HeatingCoil1", "HeatingCoil1Inlet", "HeatingCoil1Outlet"])
    assert len(group) == 4
    assert obj.num_extensible_groups() == 1
    assert obj.num_fields() == 2 + 4  # 2 fixed + 4 ext


def test_idf_object_extensible_group_field_access_by_index():
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)

    obj.push_extensible_group(["Coil:Heating:Fuel", "HeatingCoil1", "Inlet", "Outlet"])

    # Fixed fields: 0=Name, 1=Pressure Drop Curve Name
    # Ext group 0: index 2..5
    assert obj.getString(2) == "Coil:Heating:Fuel"
    assert obj.getString(3) == "HeatingCoil1"
    assert obj.getString(5) == "Outlet"


def test_idf_object_load_with_extensible_groups():
    idd_obj = make_idd_object(BRANCH_IDD)
    idf_text = """
Branch,
  CW Loop Supply Branch,   !- Name
  ,                        !- Pressure Drop Curve Name
  Pump:VariableSpeed,      !- Component 1 Object Type
  CW Circ Pump,            !- Component 1 Name
  CW Supply Inlet,         !- Component 1 Inlet Node Name
  CW Pump Outlet,          !- Component 1 Outlet Node Name
  Chiller:Electric:EIR,    !- Component 2 Object Type
  Chiller1,                !- Component 2 Name
  Chiller1 Inlet,          !- Component 2 Inlet Node Name
  Chiller1 Outlet;         !- Component 2 Outlet Node Name
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)

    assert obj.name == "CW Loop Supply Branch"
    assert obj.num_extensible_groups() == 2
    assert obj.num_fields() == 2 + 4 + 4  # 2 fixed + 2 groups of 4

    # First group
    assert obj.getString(2) == "Pump:VariableSpeed"
    assert obj.getString(5) == "CW Pump Outlet"
    # Second group
    assert obj.getString(6) == "Chiller:Electric:EIR"
    assert obj.getString(9) == "Chiller1 Outlet"


def test_idf_object_pop_extensible_group():
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.push_extensible_group(["TypeA", "NameA", "Inlet", "Outlet"])
    obj.push_extensible_group(["TypeB", "NameB", "Inlet2", "Outlet2"])

    popped = obj.pop_extensible_group()
    assert obj.num_extensible_groups() == 1
    assert popped[0].value() == "TypeB"


def test_idf_object_clear_extensible_groups():
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.push_extensible_group()
    obj.push_extensible_group()
    cleared = obj.clear_extensible_groups()
    assert len(cleared) == 2
    assert obj.num_extensible_groups() == 0


def test_idf_object_push_extensible_non_extensible_raises():
    idd_obj = make_idd_object(ZONE_IDD)  # Zone is not extensible
    obj = IdfObject(idd_object=idd_obj)
    with pytest.raises(IdfObjectError):
        obj.push_extensible_group()


# ---------------------------------------------------------------------------
# Serialisation (__str__)
# ---------------------------------------------------------------------------

SIMULATION_CONTROL_7_FIELDS_IDD = """\
SimulationControl,
       \\unique-object
       \\min-fields 5
  A1 , \\field Do Zone Sizing Calculation
       \\type choice
       \\default No
       \\key Yes
       \\key No
  A2 , \\field Do System Sizing Calculation
       \\type choice
       \\default No
       \\key Yes
       \\key No
  A3 , \\field Do Plant Sizing Calculation
       \\type choice
       \\default No
       \\key Yes
       \\key No
  A4 , \\field Run Simulation for Sizing Periods
       \\type choice
       \\default Yes
       \\key Yes
       \\key No
  A5 , \\field Run Simulation for Weather File Run Periods
       \\type choice
       \\default Yes
       \\key Yes
       \\key No
  A6 , \\field Do HVAC Sizing Simulation for Sizing Periods
       \\type choice
       \\default No
       \\key Yes
       \\key No
  N1 ; \\field Maximum Number of HVAC Sizing Simulation Passes
       \\type integer
       \\minimum 1
       \\default 1
"""


def test_idf_object_str_no_fields():
    """An object with no fields serialises with a semicolon."""
    # Build a minimal IddObject with no fields
    no_field_idd = "Version;\n"
    idd_obj = make_idd_object(no_field_idd)
    obj = IdfObject(idd_object=idd_obj)
    text = str(obj)
    assert "Version;" in text


def test_idf_object_str_with_fields():
    idd_obj = make_idd_object(SIMULATION_CONTROL_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "Yes")

    text = str(obj)
    assert "SimulationControl," in text
    assert "Yes" in text
    # Last field ends with ;
    assert ";" in text


def test_idf_object_str_exact_simulation_control_explicit():
    """Serialisation must match the canonical EnergyPlus IDF format exactly."""
    idd_obj = make_idd_object(SIMULATION_CONTROL_7_FIELDS_IDD)
    idf_text = """
SimulationControl,
  No,                      !- Do Zone Sizing Calculation
  No,                      !- Do System Sizing Calculation
  No,                      !- Do Plant Sizing Calculation
  Yes,                     !- Run Simulation for Sizing Periods
  Yes,                     !- Run Simulation for Weather File Run Periods
  No,                      !- Do HVAC Sizing Simulation for Sizing Periods
  1;                       !- Maximum Number of HVAC Sizing Simulation Passes
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)

    expected = "\n".join(
        [
            "SimulationControl,",
            "  No,                      !- Do Zone Sizing Calculation",
            "  No,                      !- Do System Sizing Calculation",
            "  No,                      !- Do Plant Sizing Calculation",
            "  Yes,                     !- Run Simulation for Sizing Periods",
            "  Yes,                     !- Run Simulation for Weather File Run Periods",
            "  No,                      !- Do HVAC Sizing Simulation for Sizing Periods",
            "  1;                       !- Maximum Number of HVAC Sizing Simulation Passes",
            "",
        ]
    )

    assert str(obj) == expected


@pytest.mark.parametrize("leading", [0, 2, 4])
def test_idf_object_str_exact_simulation_control(monkeypatch, leading):
    """Serialisation matches the canonical EnergyPlus IDF format for IDF_LEADING=0 and 2."""
    from energyplus_toolkit.input.idf import idf_constants

    monkeypatch.setattr(idf_constants, "IDF_LEADING", leading)

    idd_obj = make_idd_object(SIMULATION_CONTROL_7_FIELDS_IDD)
    idf_text = """
SimulationControl,
  No,
  No,
  No,
  Yes,
  Yes,
  No,
  1;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)

    L = " " * leading
    indent = " " * (leading + idf_constants.IDF_INDENT)
    expected = "\n".join(
        [
            f"{L}SimulationControl,",
            f"{indent}No,                      !- Do Zone Sizing Calculation",
            f"{indent}No,                      !- Do System Sizing Calculation",
            f"{indent}No,                      !- Do Plant Sizing Calculation",
            f"{indent}Yes,                     !- Run Simulation for Sizing Periods",
            f"{indent}Yes,                     !- Run Simulation for Weather File Run Periods",
            f"{indent}No,                      !- Do HVAC Sizing Simulation for Sizing Periods",
            f"{indent}1;                       !- Maximum Number of HVAC Sizing Simulation Passes",
            "",
        ]
    )

    assert str(obj) == expected


def test_idf_object_str_long_value_fallback_padding():
    """Values longer than the column width get the minimum 2-space padding."""
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "Simple One Zone (Wireframe DXF)")

    first_field_line = str(obj).splitlines()[1]
    assert first_field_line == "  Simple One Zone (Wireframe DXF);  !- Name"


def test_idf_object_min_fields_fresh_object():
    """A freshly constructed Zone (min-fields 1) serialises only the Name field."""
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)

    lines = str(obj).splitlines()
    assert lines[0] == "Zone,"
    assert len(lines) == 2  # object-type + Name field (trailing \n not counted by splitlines)
    assert lines[1].endswith("!- Name")
    assert lines[1].strip().startswith(";")  # last (only) field gets semicolon


def test_idf_object_min_fields_setstring_extends():
    """Writing a field beyond min-fields extends the active count."""
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setDouble(2, 5.0)  # X Origin — index 2, beyond min-fields=1

    lines = str(obj).splitlines()
    # Fields 0 (Name), 1 (Direction), 2 (X Origin) must be present
    assert len(lines) == 4  # object-type + 3 field lines (trailing \n not counted by splitlines)
    assert "!- X Origin" in lines[3]
    assert lines[3].strip().startswith("5.0;")  # last active field gets semicolon


def test_idf_object_min_fields_parsed_5():
    """Parsing a 5-field SimulationControl (min-fields 5) serialises exactly 5 fields."""
    idd_obj = make_idd_object(SIMULATION_CONTROL_7_FIELDS_IDD)
    idf_text = """
SimulationControl,
  No,
  No,
  No,
  Yes,
  Yes;
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)

    lines = [ln for ln in str(obj).splitlines() if ln]
    assert len(lines) == 6  # object-type + 5 field lines
    assert lines[-1].endswith("Run Simulation for Weather File Run Periods")


def test_idf_object_str_roundtrip():
    """load → str should produce parseable output with the same values."""
    idd_obj = make_idd_object(ZONE_IDD)
    idf_text = "Zone,\n  ZONE ONE,\n  90,\n  1.0,\n  2.0,\n  3.0;\n"
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)

    serialized = str(obj)

    obj2 = IdfObject.load(idd_object=idd_obj, text=serialized)
    assert obj2.name == "ZONE ONE"
    assert obj2.getDouble(1) == 90.0
    assert obj2.getDouble(2) == 1.0
    assert obj2.getDouble(3) == 2.0
    assert obj2.getDouble(4) == 3.0


def test_idf_object_str_extensible_group_lifecycle():
    """Serialise before/after push_extensible_group and after clear_extensible_groups.

    Like in EnergyPlus' files, the group number is where the IDD has it: "Component 2 Object Type".
    """
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "Supply Branch")

    # Before any extensible groups: only 2 fixed fields
    assert obj._num_active_fields == 1
    expected_before = "\n".join(
        [
            "Branch,",
            "  Supply Branch;           !- Name",
            "",
        ]
    )
    assert str(obj) == expected_before

    # Push one extensible group (4 fields per group)
    obj.push_extensible_group(["Pump:VariableSpeed", "Pump", "Pump-Inlet", "Pump-Outlet"])
    assert obj._num_active_fields == 2
    expected_with_group = "\n".join(
        [
            "Branch,",
            "  Supply Branch,           !- Name",
            "  ,                        !- Pressure Drop Curve Name",
            "  Pump:VariableSpeed,      !- Component 1 Object Type",
            "  Pump,                    !- Component 1 Name",
            "  Pump-Inlet,              !- Component 1 Inlet Node Name",
            "  Pump-Outlet;             !- Component 1 Outlet Node Name",
            "",
        ]
    )
    assert str(obj) == expected_with_group

    # Push a second group: numbered 2
    obj.push_extensible_group(["Coil:Heating:Water", "Coil", "Coil-Inlet", "Coil-Outlet"])
    assert obj._num_active_fields == 2
    expected_with_two_groups = "\n".join(
        [
            "Branch,",
            "  Supply Branch,           !- Name",
            "  ,                        !- Pressure Drop Curve Name",
            "  Pump:VariableSpeed,      !- Component 1 Object Type",
            "  Pump,                    !- Component 1 Name",
            "  Pump-Inlet,              !- Component 1 Inlet Node Name",
            "  Pump-Outlet,             !- Component 1 Outlet Node Name",
            "  Coil:Heating:Water,      !- Component 2 Object Type",
            "  Coil,                    !- Component 2 Name",
            "  Coil-Inlet,              !- Component 2 Inlet Node Name",
            "  Coil-Outlet;             !- Component 2 Outlet Node Name",
            "",
        ]
    )
    assert str(obj) == expected_with_two_groups

    # Clear extensible groups: fixed fields stay active, no extensible fields
    obj.clear_extensible_groups()
    assert obj._num_active_fields == 2
    expected_after_clear = "\n".join(
        [
            "Branch,",
            "  Supply Branch,           !- Name",
            "  ;                        !- Pressure Drop Curve Name",
            "",
        ]
    )
    assert str(obj) == expected_after_clear


def test_idf_object_repr():
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "TestZone")
    r = repr(obj)
    assert "IdfObject" in r
    assert "Zone" in r
    assert "TestZone" in r


# ---------------------------------------------------------------------------
# Blank-field round-trip: fields left blank in IDF must stay blank on output
# (they must NOT be replaced by their IDD defaults)
# ---------------------------------------------------------------------------

DESIGN_DAY_LIKE_IDD = """\
DesignDayLike,
       \\min-fields 3
  A1 , \\field Name
       \\type alpha
       \\required-field
  A2 , \\field Dry-Bulb Temperature Range Modifier Type
       \\type choice
       \\default DefaultMultipliers
       \\key DefaultMultipliers
       \\key MultiplierSchedule
       \\key DifferenceSchedule
  N1 ; \\field Sky Clearness
       \\type real
       \\minimum 0.0
       \\maximum 1.2
       \\default 0.0
"""


def test_idf_object_blank_fields_not_filled_with_defaults():
    """Blank tokens parsed from an IDF must serialise as blank, not as the IDD default.

    This is the 'Dry-Bulb Temperature Range Modifier Type' case: the field was
    blank in the original IDF but the IDD default is 'DefaultMultipliers'.
    After a load → str round-trip the blank must remain blank.
    """
    idd_obj = make_idd_object(DESIGN_DAY_LIKE_IDD)
    idf_text = """\
DesignDayLike,
  My Design Day,           !- Name
  ,                        !- Dry-Bulb Temperature Range Modifier Type
  ;                        !- Sky Clearness
"""
    obj = IdfObject.load(idd_object=idd_obj, text=idf_text)

    # The choice field was blank — must not be defaulted
    assert obj.getString(1, return_default=False) is None
    # The real field was blank — must not be defaulted
    assert obj.getString(2, return_default=False) is None

    serialized = str(obj)
    lines = serialized.splitlines()

    choice_line = lines[2]  # "  ,  !- Dry-Bulb..."
    real_line = lines[3]  # "  ;  !- Sky Clearness"

    assert choice_line.strip().startswith(","), f"Expected blank choice field, got: {choice_line!r}"
    assert real_line.strip().startswith(";"), f"Expected blank real field, got: {real_line!r}"


# ---------------------------------------------------------------------------
# \format vertices: X, Y and Z of a vertex on one line, like EnergyPlus' Transition writes them
# ---------------------------------------------------------------------------

SHADING_SITE_DETAILED_IDD = """\
Shading:Site:Detailed,
       \\memo Used for shading elements such as trees
       \\extensible:3
       \\format vertices
  A1 , \\field Name
       \\required-field
       \\type alpha
  N1 , \\field Number of Vertices
       \\type integer
       \\minimum 3
       \\autocalculatable
       \\default autocalculate
  N2 , \\field Vertex 1 X-coordinate
       \\begin-extensible
       \\type real
       \\units m
  N3 , \\field Vertex 1 Y-coordinate
       \\type real
       \\units m
  N4 ; \\field Vertex 1 Z-coordinate
       \\type real
       \\units m
"""

# Its vertices are regular fields (a window has 3 or 4)
FENESTRATION_IDD = """\
FenestrationSurface:Detailed,
       \\format vertices
  A1 , \\field Name
       \\type alpha
  N1 , \\field Number of Vertices
       \\type integer
       \\autocalculatable
       \\default autocalculate
  N2 , \\field Vertex 1 X-coordinate
       \\units m
  N3 , \\field Vertex 1 Y-coordinate
       \\units m
  N4 , \\field Vertex 1 Z-coordinate
       \\units m
  N5 , \\field Vertex 2 X-coordinate
       \\units m
  N6 , \\field Vertex 2 Y-coordinate
       \\units m
  N7 ; \\field Vertex 2 Z-coordinate
       \\units m
"""

# Zone has \\format vertices, but its origin isn't a vertex
ZONE_ORIGIN_IDD = """\
Zone,
       \\format vertices
  A1 , \\field Name
       \\type alpha
  N1 , \\field X Origin
       \\units m
  N2 , \\field Y Origin
       \\units m
  N3 ; \\field Z Origin
       \\units m
"""


def test_idf_object_str_format_vertices_extensible():
    obj = IdfObject.load(make_idd_object(SHADING_SITE_DETAILED_IDD), "Shading:Site:Detailed,S,3,0,0,4.572,1,0,0,1,1,0;")
    assert str(obj) == "\n".join(
        [
            "Shading:Site:Detailed,",
            "  S,                       !- Name",
            "  3,                       !- Number of Vertices",
            "  0.0,0.0,4.572,  !- X,Y,Z ==> Vertex 1 {m}",
            "  1.0,0.0,0.0,  !- X,Y,Z ==> Vertex 2 {m}",
            "  1.0,1.0,0.0;  !- X,Y,Z ==> Vertex 3 {m}",
            "",
        ]
    )


def test_idf_object_str_format_vertices_regular_fields():
    obj = IdfObject.load(make_idd_object(FENESTRATION_IDD), "FenestrationSurface:Detailed,W,2,0,0,1,0,0,0;")
    assert str(obj) == "\n".join(
        [
            "FenestrationSurface:Detailed,",
            "  W,                       !- Name",
            "  2,                       !- Number of Vertices",
            "  0.0,0.0,1.0,  !- X,Y,Z ==> Vertex 1 {m}",
            "  0.0,0.0,0.0;  !- X,Y,Z ==> Vertex 2 {m}",
            "",
        ]
    )


def test_idf_object_str_format_vertices_zone_origin_isnt_a_vertex():
    obj = IdfObject.load(make_idd_object(ZONE_ORIGIN_IDD), "Zone,Z1,1,2,3;")
    assert str(obj) == "\n".join(
        [
            "Zone,",
            "  Z1,                      !- Name",
            "  1.0,                     !- X Origin {m}",
            "  2.0,                     !- Y Origin {m}",
            "  3.0;                     !- Z Origin {m}",
            "",
        ]
    )


def test_idf_object_str_format_vertices_custom_comment_on_z_is_kept():
    """A custom comment ends up on the last field of the line, Z: it's kept on the vertex line."""
    obj = IdfObject.load(
        make_idd_object(SHADING_SITE_DETAILED_IDD),
        "Shading:Site:Detailed,S,,\n  0,0,1,\n  1,0,0,\n  1,1,0;  ! My vertex\n",
    )
    assert str(obj).splitlines()[-1] == "  1.0,1.0,0.0;  ! My vertex"


def test_idf_object_str_format_vertices_custom_comment_on_x_keeps_one_field_per_line():
    """It can't be on the vertex line without being moved: that vertex is written one field per line."""
    obj = IdfObject.load(
        make_idd_object(SHADING_SITE_DETAILED_IDD),
        "Shading:Site:Detailed,S,,\n  0,0,1,\n  1,0,0,\n  1,  ! My X\n  1,0;\n",
    )
    assert str(obj).splitlines()[-4:] == [
        "  1.0,0.0,0.0,  !- X,Y,Z ==> Vertex 2 {m}",
        "  1.0,                     ! My X",
        "  1.0,                     !- Vertex 3 Y-coordinate {m}",
        "  0.0;                     !- Vertex 3 Z-coordinate {m}",
    ]


# ---------------------------------------------------------------------------
# \format compactSchedule: "Until: HH:MM" and its value on one line, like EnergyPlus' Transition writes them
# ---------------------------------------------------------------------------

SCHEDULE_COMPACT_IDD = """\
Schedule:Compact,
       \\extensible:1
       \\format compactSchedule
  A1 , \\field Name
       \\required-field
       \\type alpha
  A2 , \\field Schedule Type Limits Name
       \\type object-list
       \\object-list ScheduleTypeLimitsNames
  A3 , \\field Field 1
       \\begin-extensible
       \\type alpha
"""


def test_idf_object_str_format_compact_schedule():
    obj = IdfObject.load(
        make_idd_object(SCHEDULE_COMPACT_IDD),
        "Schedule:Compact,Sch,Fraction,Through: 12/31,For: AllDays,Until: 08:00,0.0,Until: 24:00,1.0;",
    )
    assert str(obj) == "\n".join(
        [
            "Schedule:Compact,",
            "  Sch,                     !- Name",
            "  Fraction,                !- Schedule Type Limits Name",
            "  Through: 12/31,          !- Field 1",
            "  For: AllDays,            !- Field 2",
            "  Until: 08:00,0.0,        !- Field 3",
            "  Until: 24:00,1.0;        !- Field 5",
            "",
        ]
    )


def test_idf_object_str_format_compact_schedule_custom_comment_on_value_is_kept():
    """A custom comment ends up on the last field of the line, the value: it's kept on the Until line."""
    obj = IdfObject.load(
        make_idd_object(SCHEDULE_COMPACT_IDD),
        "Schedule:Compact,Sch,,Through: 12/31,For: AllDays,\n  Until: 24:00,1.0;  ! Always on\n",
    )
    assert str(obj).splitlines()[-1] == "  Until: 24:00,1.0;        ! Always on"


def test_idf_object_str_format_compact_schedule_custom_comment_on_until_keeps_one_field_per_line():
    """It can't be on the Until line without being moved: the Until field and its value stay on their own lines."""
    obj = IdfObject.load(
        make_idd_object(SCHEDULE_COMPACT_IDD),
        "Schedule:Compact,Sch,,Through: 12/31,For: AllDays,\n  Until: 24:00,  ! End of day\n  1.0;\n",
    )
    assert str(obj).splitlines()[-2:] == [
        "  Until: 24:00,            ! End of day",
        "  1.0;                     !- Field 4",
    ]


def test_idf_object_str_format_compact_schedule_until_last_field():
    """An "Until" field with no value after it (invalid, but it must not be lost) is written alone."""
    obj = IdfObject.load(
        make_idd_object(SCHEDULE_COMPACT_IDD), "Schedule:Compact,Sch,,Through: 12/31,For: AllDays,Until: 24:00;"
    )
    assert str(obj).splitlines()[-1] == "  Until: 24:00;            !- Field 3"


# ---------------------------------------------------------------------------
# \format FluidProperty and Spectral: the data fields (named with a number) several per line, without comments, like
# EnergyPlus' Transition writes them
# ---------------------------------------------------------------------------

FLUID_TEMPERATURES_IDD = (
    "FluidProperties:Temperatures,\n       \\format FluidProperty\n  A1 , \\field Name\n"
    + "".join(f"  N{i} {';' if i == 9 else ','} \\field Temperature {i}\n       \\units C\n" for i in range(1, 10))
)

SPECTRAL_IDD = "MaterialProperty:GlazingSpectralData,\n       \\format Spectral\n  A1 , \\field Name\n" + "".join(
    f"  N{4 * (g - 1) + i} {';' if g == 2 and i == 4 else ','} \\field {name} {g}\n"
    for g in (1, 2)
    for i, name in enumerate(["Wavelength", "Transmittance", "Front Reflectance", "Back Reflectance"], start=1)
)


def test_idf_object_str_format_fluid_property():
    """7 values per line, the last line has what's left."""
    obj = IdfObject.load(make_idd_object(FLUID_TEMPERATURES_IDD), "FluidProperties:Temperatures,T,1,2,3,4,5,6,7,8,9;")
    assert str(obj) == "\n".join(
        [
            "FluidProperties:Temperatures,",
            "  T,                       !- Name",
            "  1.0,2.0,3.0,4.0,5.0,6.0,7.0,",
            "  8.0,9.0;",
            "",
        ]
    )


def test_idf_object_str_format_spectral():
    """4 values per line: wavelength, transmittance, front and back reflectance."""
    obj = IdfObject.load(
        make_idd_object(SPECTRAL_IDD), "MaterialProperty:GlazingSpectralData,S,0.3,0,0.045,0.045,0.31,0,0.044,0.044;"
    )
    assert str(obj) == "\n".join(
        [
            "MaterialProperty:GlazingSpectralData,",
            "  S,                       !- Name",
            "  0.3,0.0,0.045,0.045,",
            "  0.31,0.0,0.044,0.044;",
            "",
        ]
    )


def test_idf_object_str_format_values_per_line_custom_comment_on_last_value_is_kept():
    """A custom comment ends up on the last field of the line: it's kept on the line of values."""
    obj = IdfObject.load(
        make_idd_object(SPECTRAL_IDD),
        "MaterialProperty:GlazingSpectralData,S,\n  0.3,0,0.045,0.045,  ! UV\n  0.31,0,0.044,0.044;\n",
    )
    assert str(obj).splitlines()[2:4] == ["  0.3,0.0,0.045,0.045,  ! UV", "  0.31,0.0,0.044,0.044;"]


def test_idf_object_str_format_values_per_line_custom_comment_inside_keeps_one_field_per_line():
    """It can't be on the line of values without being moved: those values are written one per line, the next ones
    still several per line."""
    obj = IdfObject.load(
        make_idd_object(SPECTRAL_IDD),
        "MaterialProperty:GlazingSpectralData,S,\n  0.3,  ! UV\n  0,0.045,0.045,\n  0.31,0,0.044,0.044;\n",
    )
    assert str(obj).splitlines()[2:7] == [
        "  0.3,                     ! UV",
        "  0.0,                     !- Transmittance 1",
        "  0.045,                   !- Front Reflectance 1",
        "  0.045,                   !- Back Reflectance 1",
        "  0.31,0.0,0.044,0.044;",
    ]

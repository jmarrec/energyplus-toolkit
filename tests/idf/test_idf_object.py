import pytest

from energyplus_parser.idd.idd_object import IddObject
from energyplus_parser.idf.idf_field import (
    AlphaField,
    ChoiceField,
    FieldValidationError,
    IntegerField,
    NumericMode,
    RealField,
)
from energyplus_parser.idf.idf_object import IdfObject, IdfObjectError


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
# setString / getString by index
# ---------------------------------------------------------------------------


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
# Extensible groups
# ---------------------------------------------------------------------------


def test_idf_object_push_extensible_group():
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)

    assert not obj.idd_object.properties.extensible or obj.num_extensible_groups() == 0

    group = obj.push_extensible_group(
        ["Coil:Heating:Fuel", "HeatingCoil1", "HeatingCoil1Inlet", "HeatingCoil1Outlet"]
    )
    assert len(group) == 4
    assert obj.num_extensible_groups() == 1
    assert obj.num_fields() == 2 + 4  # 2 fixed + 4 ext


def test_idf_object_extensible_group_field_access_by_index():
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)

    obj.push_extensible_group(
        ["Coil:Heating:Fuel", "HeatingCoil1", "Inlet", "Outlet"]
    )

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

    expected = "\n".join([
        "SimulationControl,",
        "  No,                      !- Do Zone Sizing Calculation",
        "  No,                      !- Do System Sizing Calculation",
        "  No,                      !- Do Plant Sizing Calculation",
        "  Yes,                     !- Run Simulation for Sizing Periods",
        "  Yes,                     !- Run Simulation for Weather File Run Periods",
        "  No,                      !- Do HVAC Sizing Simulation for Sizing Periods",
        "  1;                       !- Maximum Number of HVAC Sizing Simulation Passes",
        "",
    ])

    assert str(obj) == expected

@pytest.mark.parametrize("leading", [0, 2, 4])
def test_idf_object_str_exact_simulation_control(monkeypatch, leading):
    """Serialisation matches the canonical EnergyPlus IDF format for IDF_LEADING=0 and 2."""
    from energyplus_parser.idf import idf_constants

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
    I = " " * (leading + idf_constants.IDF_INDENT)
    expected = "\n".join([
        f"{L}SimulationControl,",
        f"{I}No,                      !- Do Zone Sizing Calculation",
        f"{I}No,                      !- Do System Sizing Calculation",
        f"{I}No,                      !- Do Plant Sizing Calculation",
        f"{I}Yes,                     !- Run Simulation for Sizing Periods",
        f"{I}Yes,                     !- Run Simulation for Weather File Run Periods",
        f"{I}No,                      !- Do HVAC Sizing Simulation for Sizing Periods",
        f"{I}1;                       !- Maximum Number of HVAC Sizing Simulation Passes",
        "",
    ])

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

    lines = [l for l in str(obj).splitlines() if l]
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
    """Serialise before/after push_extensible_group and after clear_extensible_groups."""
    idd_obj = make_idd_object(BRANCH_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "Supply Branch")

    # Before any extensible groups: only 2 fixed fields
    assert obj._num_active_fields == 1
    expected_before = "\n".join([
        "Branch,",
        "  Supply Branch;           !- Name",
        "",
    ])
    assert str(obj) == expected_before

    # Push one extensible group (4 fields per group)
    obj.push_extensible_group(["Pump:VariableSpeed", "Pump", "Pump-Inlet", "Pump-Outlet"])
    assert obj._num_active_fields == 2
    expected_with_group = "\n".join([
        "Branch,",
        "  Supply Branch,           !- Name",
        "  ,                        !- Pressure Drop Curve Name",
        "  Pump:VariableSpeed,      !- Component Object Type",
        "  Pump,                    !- Component Name",
        "  Pump-Inlet,              !- Component Inlet Node Name",
        "  Pump-Outlet;             !- Component Outlet Node Name",
        "",
    ])
    assert str(obj) == expected_with_group

    # Clear extensible groups: fixed fields stay active, no extensible fields
    obj.clear_extensible_groups()
    assert obj._num_active_fields == 2
    expected_after_clear = "\n".join([
        "Branch,",
        "  Supply Branch,           !- Name",
        "  ;                        !- Pressure Drop Curve Name",
        "",
    ])
    assert str(obj) == expected_after_clear





def test_idf_object_repr():
    idd_obj = make_idd_object(ZONE_IDD)
    obj = IdfObject(idd_object=idd_obj)
    obj.setString(0, "TestZone")
    r = repr(obj)
    assert "IdfObject" in r
    assert "Zone" in r
    assert "TestZone" in r

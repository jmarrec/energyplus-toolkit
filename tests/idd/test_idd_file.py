from energyplus_parser.idd.idd_constants import COMMENT_ONLY_OBJECT_NAME
from energyplus_parser.idd.idd_file import IddFile
from energyplus_parser.idd.idd_object import IddObject


def header() -> str:
    return r"""!IDD_Version 25.2.0
!IDD_BUILD TBD
! **************************************************************************
! This file is the Input Data Dictionary (IDD) for EnergyPlus.
! The IDD defines the syntax and data model for each type of input "Object."
! Lines in EnergyPlus input files (and IDD) are limited to 500 characters.
!
!  \begin-extensible See previous item, marks beginning of extensible fields in
!                   an object.
! **************************************************************************"""


def idd_text() -> str:
    return rf"""{header()}

\group Simulation Parameters

Version,
      \memo Specifies the EnergyPlus version of the IDF file.
      \unique-object
      \format singleLine
      \min-fields 1
  A1 ; \field Version Identifier
      \default 25.2

Building,
       \memo Describes parameters that are used during the simulation
       \memo of the building. There are necessary correlations between the entries for
       \memo this object and some entries in the Site:WeatherStation and
       \memo Site:HeightVariation objects, specifically the Terrain field.
       \unique-object
       \required-object
       \min-fields 8
  A1 , \field Name
       \retaincase
       \default NONE
  N1 , \field North Axis
       \note degrees from true North
       \units deg
       \type real
       \default 0.0
  A2 , \field Terrain
       \note  Country=FlatOpenCountry | Suburbs=CountryTownsSuburbs | City=CityCenter | Ocean=body of water (5km) | Urban=Urban-Industrial-Forest
       \type choice
       \key Country
       \key Suburbs
       \key City
       \key Ocean
       \key Urban
       \default Suburbs
  N2 , \field Loads Convergence Tolerance Value
       \note Loads Convergence Tolerance Value is a change in load from one warmup day to the next
       \type real
       \minimum> 0.0
       \maximum .5
       \default .04
       \units W
  N3 , \field Temperature Convergence Tolerance Value
       \units deltaC
       \type real
       \minimum> 0.0
       \maximum .5
       \default .4
  A3 , \field Solar Distribution
       \note  MinimalShadowing | FullExterior | FullInteriorAndExterior | FullExteriorWithReflections | FullInteriorAndExteriorWithReflections
       \type choice
       \key MinimalShadowing
       \key FullExterior
       \key FullInteriorAndExterior
       \key FullExteriorWithReflections
       \key FullInteriorAndExteriorWithReflections
       \default FullExterior
  N4 , \field Maximum Number of Warmup Days
       \note EnergyPlus will only use as many warmup days as needed to reach convergence tolerance.
       \note This field's value should NOT be set less than 25.
       \type integer
       \minimum> 0
       \default 25
  N5 ; \field Minimum Number of Warmup Days
       \note The minimum number of warmup days that produce enough temperature and flux history
       \note to start EnergyPlus simulation for all reference buildings was suggested to be 6.
       \note However this can lead to excessive run times as warmup days can be repeated needlessly.
       \note For faster execution rely on the convergence criteria to detect when warmup is complete.
       \note When this field is greater than the maximum warmup days defined previous field
       \note the maximum number of warmup days will be reset to the minimum value entered here.
       \note Warmup days will be set to be the value you entered. The default is 1.
       \type integer
       \minimum> 0
       \default 1


\group Compliance Objects

Compliance:Building,
       \memo Building level inputs related to compliance to building standards, building codes, and beyond energy code programs.
       \unique-object
       \min-fields 1
  N1;  \field Building Rotation for Appendix G
       \note Additional degrees of rotation to be used with the requirement in ASHRAE Standard 90.1 Appendix G
       \note that states that the baseline building should be rotated in four directions.
       \units deg
       \type real
       \default 0.0

\group Thermal Zones and Surfaces

SpaceList,
       \memo Defines a list of Spaces which can be referenced as a group. The SpaceList name
       \memo may be used elsewhere in the input to apply a parameter to all Spaces in the list.
       \memo SpaceLists can be used effectively with the following objects: InternalMass, People, Lights,
       \memo ElectricEquipment, GasEquipment, HotWaterEquipment, and others.
       \min-fields 2
       \extensible:1
  A1 , \field Name
       \note Name of the SpaceList.
       \note This name must be unique across Zone, Space, ZoneList, and SpaceList names.
       \required-field
       \type alpha
       \reference SpaceListNames
       \reference SpaceAndSpaceListNames
       \reference ZoneAndZoneListAndSpaceAndSpaceListNames
  A2 ; \field Space 1 Name
       \begin-extensible
       \required-field
       \type object-list
       \object-list SpaceNames
"""


def test_parse_idd_file():
    idd_file = IddFile.fromString(text=idd_text())
    assert idd_file.version == "25.2.0"
    assert idd_file.build == "TBD"
    assert idd_file.header == header()
    assert len(idd_file.objects) == 5  # Including the fake comment-only object

    comment_only_obj = idd_file.objects[0]
    assert isinstance(comment_only_obj, IddObject)
    assert comment_only_obj.name == COMMENT_ONLY_OBJECT_NAME

    version_obj = idd_file.objects[1]
    assert isinstance(version_obj, IddObject)
    assert version_obj.name == "Version"

    building_obj = idd_file.objects[2]
    assert isinstance(building_obj, IddObject)
    assert building_obj.name == "Building"

    compliance_building_obj = idd_file.objects[3]
    assert isinstance(compliance_building_obj, IddObject)
    assert compliance_building_obj.name == "Compliance:Building"

    space_list_obj = idd_file.objects[4]
    assert isinstance(space_list_obj, IddObject)
    assert space_list_obj.name == "SpaceList"

    assert idd_file.groups() == {"", "Simulation Parameters", "Compliance Objects", "Thermal Zones and Surfaces"}

    assert idd_file.versionObject() is not None
    assert idd_file.versionObject() == version_obj

    # Test getObjectsInGroup
    assert idd_file.getObjectsInGroup("Simulation Parameters") == [version_obj, building_obj]

    assert idd_file.getObjectsInGroup("Compliance Objects") == [compliance_building_obj]

    assert len(idd_file.getObjectsInGroup("")) == 1  # CommentOnly object

    assert len(idd_file.getObjectsInGroup("Non existing group")) == 0

    # Test getObject
    assert idd_file.getObject("Version") == version_obj
    # It works case insensitively
    assert idd_file.getObject("compliance:building") == compliance_building_obj
    assert idd_file.getObject("Non existing object") is None

    assert idd_file.uniqueObjects() == [version_obj, building_obj, compliance_building_obj]

    assert idd_file.requiredObjects() == [building_obj]

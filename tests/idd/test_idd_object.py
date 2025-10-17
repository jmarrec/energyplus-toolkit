from energyplus_parser.constants import BLOCK_INDENT
from energyplus_parser.idd.idd_field import IddField
from energyplus_parser.idd.idd_object import IddObject, IddObjectProperties


def test_idd_object_properties() -> None:
    obj_props = IddObjectProperties()

    obj_props.memo = "This is a test memo."
    obj_props.unique = True
    obj_props.required = True
    obj_props.obsolete = False
    obj_props.hasUrl = False
    obj_props.extensible = True
    obj_props.numExtensible = 2
    obj_props.numExtensibleGroupsRequired = 1
    obj_props.format = ""
    obj_props.minFields = 5
    obj_props.maxFields = 10
    expected = "\n".join(
        [
            f'{BLOCK_INDENT}\\memo This is a test memo.',
            f'{BLOCK_INDENT}\\unique-object',
            f'{BLOCK_INDENT}\\required-object',
            f'{BLOCK_INDENT}\\extensible:2',
            f'{BLOCK_INDENT}\\min-fields 5',
            f'{BLOCK_INDENT}\\max-fields 10',
        ]
    )
    assert str(obj_props) == expected


def test_parse_idd_object_required_unique() -> None:
    name = "Building"
    group = "Simulation Parameters"
    ori_text = r"""Building,
       \memo Describes parameters that are used during the simulation
       \memo of the building. There are necessary correlations between the entries for
       \memo this object and some entries in the Site:WeatherStation and
       \memo Site:HeightVariation objects, specifically the Terrain field.
       \unique-object
       \required-object
       \min-fields 8
  A1 , \field Name
       \type alpha
       \retaincase
       \default NONE
  N1 , \field North Axis
       \note degrees from true North
       \type real
       \units deg
       \default 0.0
  A2 , \field Terrain
       \note Country=FlatOpenCountry | Suburbs=CountryTownsSuburbs | City=CityCenter | Ocean=body of water (5km) | Urban=Urban-Industrial-Forest
       \type choice
       \default Suburbs
       \key Country
       \key Suburbs
       \key City
       \key Ocean
       \key Urban
  N2 , \field Loads Convergence Tolerance Value
       \note Loads Convergence Tolerance Value is a change in load from one warmup day to the next
       \type real
       \units W
       \minimum> 0.0
       \maximum 0.5
       \default .04
  N3 , \field Temperature Convergence Tolerance Value
       \type real
       \units deltaC
       \minimum> 0.0
       \maximum 0.5
       \default .4
  A3 , \field Solar Distribution
       \note MinimalShadowing | FullExterior | FullInteriorAndExterior | FullExteriorWithReflections | FullInteriorAndExteriorWithReflections
       \type choice
       \default FullExterior
       \key MinimalShadowing
       \key FullExterior
       \key FullInteriorAndExterior
       \key FullExteriorWithReflections
       \key FullInteriorAndExteriorWithReflections
  N4 , \field Maximum Number of Warmup Days
       \note EnergyPlus will only use as many warmup days as needed to reach convergence tolerance.
       \note This field's value should NOT be set less than 25.
       \type integer
       \minimum> 0.0
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
       \minimum> 0.0
       \default 1
"""
    idd_obj = IddObject.load(group=group, object_lines=ori_text.splitlines())

    assert idd_obj.name == name
    assert idd_obj.group == group
    assert len(idd_obj.fields) == 8
    assert idd_obj.fields[0].name == "Name"
    assert idd_obj.fields[1].name == "North Axis"
    assert idd_obj.fields[2].name == "Terrain"
    assert idd_obj.fields[3].name == "Loads Convergence Tolerance Value"
    assert idd_obj.fields[4].name == "Temperature Convergence Tolerance Value"
    assert idd_obj.fields[5].name == "Solar Distribution"
    assert idd_obj.fields[6].name == "Maximum Number of Warmup Days"
    assert idd_obj.fields[7].name == "Minimum Number of Warmup Days"

    for i, f in enumerate(idd_obj.fields):
        if i < 7:
            assert not f.is_last_field
        else:
            assert f.is_last_field

    assert len(idd_obj.extensible_fields) == 0

    obj_props = idd_obj.properties

    assert (
        obj_props.memo
        == 'Describes parameters that are used during the simulation\nof the building. There are necessary correlations between the entries for\nthis object and some entries in the Site:WeatherStation and\nSite:HeightVariation objects, specifically the Terrain field.'
    )
    assert obj_props.unique
    assert obj_props.required
    assert not obj_props.obsolete
    assert not obj_props.hasUrl
    assert obj_props.format == ""

    assert not obj_props.extensible
    assert obj_props.numExtensible == 0

    assert obj_props.minFields == 8
    assert obj_props.numExtensibleGroupsRequired == 0
    assert obj_props.maxFields is None

    assert str(idd_obj) == ori_text


def test_parse_idd_object_with_one_extensible() -> None:
    name = "Site:SpectrumData"
    group = "Simulation Parameters"
    ori_text = r"""Site:SpectrumData,
       \memo Spectrum Data Type is followed by up to 107 sets of normal-incidence measured values of
       \memo [wavelength, spectrum] for wavelengths covering the solar (0.25 to 2.5 microns) or visible
       \memo spectrum (0.38 to 0.78 microns)
       \extensible:2
       \min-fields 8
  A1 , \field Name
       \type alpha
       \reference SpectrumDataNames
  A2 , \field Spectrum Data Type
       \type choice
       \key Solar
       \key Visible
  N1 , \field Wavelength
       \type real
       \begin-extensible
       \units micron
  N2 ; \field Spectrum
       \type real
"""

    idd_obj = IddObject.load(group=group, object_lines=ori_text.splitlines())

    assert idd_obj.name == name
    assert idd_obj.group == group
    assert len(idd_obj.fields) == 2
    assert idd_obj.fields[0].name == "Name"
    assert idd_obj.fields[1].name == "Spectrum Data Type"
    assert len(idd_obj.extensible_fields) == 2
    assert idd_obj.extensible_fields[0].name == "Wavelength"
    assert idd_obj.extensible_fields[1].name == "Spectrum"

    obj_props = idd_obj.properties

    assert (
        obj_props.memo
        == "Spectrum Data Type is followed by up to 107 sets of normal-incidence measured values of\n[wavelength, spectrum] for wavelengths covering the solar (0.25 to 2.5 microns) or visible\nspectrum (0.38 to 0.78 microns)"
    )
    assert not obj_props.unique
    assert not obj_props.required
    assert not obj_props.obsolete
    assert not obj_props.hasUrl
    assert obj_props.format == ""

    assert obj_props.extensible
    assert obj_props.numExtensible == 2

    assert obj_props.minFields == 8
    assert obj_props.numExtensibleGroupsRequired == 3  # 2 non Extensible + 3 groups of 2 to get 8
    assert obj_props.maxFields is None

    assert str(idd_obj) == ori_text


def test_parse_idd_object_with_extra_extensible_fields() -> None:
    """A test for an IDD Object that has a bunch of extra fields just to please IDF Editor."""
    name = "Site:SpectrumData"
    group = "Simulation Parameters"
    ori_text = r"""Site:SpectrumData,
       \min-fields 8
       \memo Spectrum Data Type is followed by up to 107 sets of normal-incidence measured values of
       \memo [wavelength, spectrum] for wavelengths covering the solar (0.25 to 2.5 microns) or visible
       \memo spectrum (0.38 to 0.78 microns)
       \extensible:2
  A1 , \field Name
       \required-field
       \type alpha
       \reference SpectrumDataNames
  A2 , \field Spectrum Data Type
       \required-field
       \type choice
       \key Solar
       \key Visible
  N1 , \field Wavelength 1
       \type real
       \units micron
  N2 , \field Spectrum 1
       \type real
  N3 , \field Wavelength 2
       \type real
       \units micron
  N4 , \field Spectrum 2
       \type real
  N5 , \field Wavelength 3
       \begin-extensible
       \type real
       \units micron
  N6 , \field Spectrum 3
       \type real
  N7 , N8,       \note fields as indicated
  N9 , N10,      \note fields as indicated
  N11, N12,     \note fields as indicated
  N13, N14,     \note fields as indicated
  N15, N16,     \note fields as indicated
  N17, N18;     \note fields as indicated
"""

    idd_obj = IddObject.load(group=group, object_lines=ori_text.splitlines())

    assert idd_obj.name == name
    assert idd_obj.group == group
    assert len(idd_obj.fields) == 6
    assert idd_obj.fields[0].name == "Name"
    assert idd_obj.fields[1].name == "Spectrum Data Type"
    assert [x.name for x in idd_obj.fields] == [
        "Name",
        "Spectrum Data Type",
        "Wavelength 1",
        "Spectrum 1",
        "Wavelength 2",
        "Spectrum 2",
    ]
    assert len(idd_obj.extensible_fields) == 2
    assert idd_obj.extensible_fields[0].name == "Wavelength"
    assert idd_obj.extensible_fields[1].name == "Spectrum"


def test_parse_idd_object_weird_ground():
    name = "GroundHeatTransfer:Slab:XFACE"
    group = "Detailed Ground Heat Transfer"
    ori_text = r"""GroundHeatTransfer:Slab:XFACE,
       \memo This is only needed when using manual gridding (not recommended)
       \memo XFACE: X Direction cell face coordinates: m
  N1, N2, N3, N4, N5, N6, N7, N8, N9, N10, N11, N12, N13, N14,                  \note fields as indicated
  N15, N16, N17, N18, N19, N20, N21, N22, N23, N24, N25, N26, N27, N28, N29,    \note fields as indicated
  N30, N31, N32, N33, N34, N35, N36, N37, N38, N39, N40;                        \note fields as indicated
"""

    idd_obj = IddObject.load(group=group, object_lines=ori_text.splitlines())
    assert idd_obj.name == name
    assert idd_obj.group == group
    assert len(idd_obj.fields) == 40

    expected_str = r"""GroundHeatTransfer:Slab:XFACE,
       \memo This is only needed when using manual gridding (not recommended)
       \memo XFACE: X Direction cell face coordinates: m
  N1 , \field N1
       \note fields as indicated
       \type real
  N2 , \field N2
       \note fields as indicated
       \type real
  N3 , \field N3
       \note fields as indicated
       \type real
  N4 , \field N4
       \note fields as indicated
       \type real
  N5 , \field N5
       \note fields as indicated
       \type real
  N6 , \field N6
       \note fields as indicated
       \type real
  N7 , \field N7
       \note fields as indicated
       \type real
  N8 , \field N8
       \note fields as indicated
       \type real
  N9 , \field N9
       \note fields as indicated
       \type real
  N10, \field N10
       \note fields as indicated
       \type real
  N11, \field N11
       \note fields as indicated
       \type real
  N12, \field N12
       \note fields as indicated
       \type real
  N13, \field N13
       \note fields as indicated
       \type real
  N14, \field N14
       \note fields as indicated
       \type real
  N15, \field N15
       \note fields as indicated
       \type real
  N16, \field N16
       \note fields as indicated
       \type real
  N17, \field N17
       \note fields as indicated
       \type real
  N18, \field N18
       \note fields as indicated
       \type real
  N19, \field N19
       \note fields as indicated
       \type real
  N20, \field N20
       \note fields as indicated
       \type real
  N21, \field N21
       \note fields as indicated
       \type real
  N22, \field N22
       \note fields as indicated
       \type real
  N23, \field N23
       \note fields as indicated
       \type real
  N24, \field N24
       \note fields as indicated
       \type real
  N25, \field N25
       \note fields as indicated
       \type real
  N26, \field N26
       \note fields as indicated
       \type real
  N27, \field N27
       \note fields as indicated
       \type real
  N28, \field N28
       \note fields as indicated
       \type real
  N29, \field N29
       \note fields as indicated
       \type real
  N30, \field N30
       \note fields as indicated
       \type real
  N31, \field N31
       \note fields as indicated
       \type real
  N32, \field N32
       \note fields as indicated
       \type real
  N33, \field N33
       \note fields as indicated
       \type real
  N34, \field N34
       \note fields as indicated
       \type real
  N35, \field N35
       \note fields as indicated
       \type real
  N36, \field N36
       \note fields as indicated
       \type real
  N37, \field N37
       \note fields as indicated
       \type real
  N38, \field N38
       \note fields as indicated
       \type real
  N39, \field N39
       \note fields as indicated
       \type real
  N40; \field N40
       \note fields as indicated
       \type real
"""

    assert str(idd_obj) == expected_str

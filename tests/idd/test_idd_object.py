import pytest

from energyplus_toolkit.input.idd.idd_constants import BLOCK_INDENT
from energyplus_toolkit.input.idd.idd_field import IddFieldParseError
from energyplus_toolkit.input.idd.idd_object import IddObject, IddObjectFormat, IddObjectProperties


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
    obj_props.format = None
    obj_props.minFields = 5
    obj_props.maxFields = 10
    expected = "\n".join(
        [
            f'{BLOCK_INDENT}\\unique-object',
            f'{BLOCK_INDENT}\\required-object',
            f'{BLOCK_INDENT}\\memo This is a test memo.',
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
       \unique-object
       \required-object
       \memo Describes parameters that are used during the simulation
       \memo of the building. There are necessary correlations between the entries for
       \memo this object and some entries in the Site:WeatherStation and
       \memo Site:HeightVariation objects, specifically the Terrain field.
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
        obj_props.memo == 'Describes parameters that are used during the simulation\n'
        'of the building. There are necessary correlations between the entries for\n'
        'this object and some entries in the Site:WeatherStation and\n'
        'Site:HeightVariation objects, specifically the Terrain field.'
    )
    assert obj_props.unique
    assert obj_props.required
    assert not obj_props.obsolete
    assert not obj_props.hasUrl
    assert obj_props.format is None

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
       \begin-extensible
       \type real
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
        obj_props.memo == "Spectrum Data Type is followed by up to 107 sets of normal-incidence measured values of\n"
        "[wavelength, spectrum] for wavelengths covering the solar (0.25 to 2.5 microns) or visible\n"
        "spectrum (0.38 to 0.78 microns)"
    )
    assert not obj_props.unique
    assert not obj_props.required
    assert not obj_props.obsolete
    assert not obj_props.hasUrl
    assert obj_props.format is None

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
    # The name has no group number. The first extensible group is the 3rd one: the first 2 are regular fields, so the
    # groups are numbered from 3
    assert [x.name for x in idd_obj.extensible_fields] == ["Wavelength", "Spectrum"]
    assert [x.name_for_group(0) for x in idd_obj.extensible_fields] == ["Wavelength 3", "Spectrum 3"]
    assert [x.name_for_group(1) for x in idd_obj.extensible_fields] == ["Wavelength 4", "Spectrum 4"]


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

    # Fields declared without names are written back compactly, still without names (no made-up "\\field N1")
    expected_str = r"""GroundHeatTransfer:Slab:XFACE,
       \memo This is only needed when using manual gridding (not recommended)
       \memo XFACE: X Direction cell face coordinates: m
  N1, N2, N3, N4, N5, N6, N7, N8, N9, N10,  \note fields as indicated
  N11, N12, N13, N14, N15, N16, N17, N18, N19, N20,  \note fields as indicated
  N21, N22, N23, N24, N25, N26, N27, N28, N29, N30,  \note fields as indicated
  N31, N32, N33, N34, N35, N36, N37, N38, N39, N40;  \note fields as indicated
"""

    assert str(idd_obj) == expected_str


def assert_field_ids_consecutive(idd_text: str, expected_last: dict[str, int]) -> None:
    """Every A / N field id is written once, numbered 1, 2, 3... separately for A and N."""
    import re

    for letter, last in expected_last.items():
        ids = [int(m) for m in re.findall(rf"\b{letter}(\d+)\s*[,;]", idd_text)]
        assert ids == list(range(1, last + 1)), f"{letter} fields: {ids}"


def test_extra_extensible_fields_numbering_with_two_fields_per_group() -> None:
    """Site:SpectrumData: the extra fields of a 2-field group (Wavelength, Spectrum) are N7, N8, N9... not N6, N7, N7..."""
    ori_text = r"""Site:SpectrumData,
       \min-fields 8
       \extensible:2
  A1 , \field Name
       \required-field
       \type alpha
  A2 , \field Spectrum Data Type
       \required-field
       \type choice
       \key Solar
       \key Visible
  N1 , \field Wavelength 1
       \type real
  N2 , \field Spectrum 1
       \type real
  N3 , \field Wavelength 2
       \begin-extensible
       \type real
  N4 , \field Spectrum 2
       \type real
  N5 , N6,       \note fields as indicated
  N7 , N8,       \note fields as indicated
  N9 , N10;      \note fields as indicated
"""
    idd_obj = IddObject.load(group="Simulation Parameters", object_lines=ori_text.splitlines())
    assert idd_obj._original_number_of_fields == 12
    assert_field_ids_consecutive(str(idd_obj), {"A": 2, "N": 10})


def test_extra_extensible_fields_numbering_with_mixed_group() -> None:
    """A group (A, N): the next groups are A3, N2 then A4, N3, each letter numbered on its own."""
    ori_text = r"""Some:Object,
       \extensible:2
  A1 , \field Name
       \type alpha
  A2 , \field Thing 1 Name
       \begin-extensible
       \type alpha
  N1 , \field Thing 1 Value
       \type real
  A3 , N2 , A4 , N3;
"""
    idd_obj = IddObject.load(group="Test", object_lines=ori_text.splitlines())
    assert idd_obj._original_number_of_fields == 7
    assert_field_ids_consecutive(str(idd_obj), {"A": 4, "N": 3})


def test_parse_idd_preserve_useless_fields_to_please_idfeditor():
    group = "Air Distribution"
    ori_text = r"""AirLoopHVAC:ZoneSplitter,
       \memo Split one air stream into N outlet streams (currently 500 per air loop, but extensible). Node names
       \memo cannot be duplicated within a single zone splitter (AirLoopHVAC:ZoneSplitter) list.
       \extensible:1
  A1 , \field Name
       \type alpha
       \reference SupplyPathComponentNames
  A2 , \field Inlet Node Name
       \type node
  A3 , \field Outlet Node Name
       \begin-extensible
       \type node
  A4  , A5  , A6  , A7  , A8  , A9  , A10 , A11 , A12 , A13 ,
  A14 , A15 , A16 , A17 , A18 , A19 , A20 , A21 , A22 , A23 ,
  A24 , A25 , A26 , A27 , A28 , A29 , A30 , A31 , A32 , A33 ,
  A34 , A35 , A36 , A37 , A38 , A39 , A40 , A41 , A42 , A43 ,
  A44 , A45 , A46 , A47 , A48 , A49 , A50 , A51 , A52 , A53 ,
  A54 , A55 , A56 , A57 , A58 , A59 , A60 , A61 , A62 , A63 ,
  A64 , A65 , A66 , A67 , A68 , A69 , A70 , A71 , A72 , A73 ,
  A74 , A75 , A76 , A77 , A78 , A79 , A80 , A81 , A82 , A83 ,
  A84 , A85 , A86 , A87 , A88 , A89 , A90 , A91 , A92 , A93 ,
  A94 , A95 , A96 , A97 , A98 , A99 , A100, A101, A102, A103,
  A104, A105, A106, A107, A108, A109, A110, A111, A112, A113,
  A114, A115, A116, A117, A118, A119, A120, A121, A122, A123,
  A124, A125, A126, A127, A128, A129, A130, A131, A132, A133,
  A134, A135, A136, A137, A138, A139, A140, A141, A142, A143,
  A144, A145, A146, A147, A148, A149, A150, A151, A152, A153,
  A154, A155, A156, A157, A158, A159, A160, A161, A162, A163,
  A164, A165, A166, A167, A168, A169, A170, A171, A172, A173,
  A174, A175, A176, A177, A178, A179, A180, A181, A182, A183,
  A184, A185, A186, A187, A188, A189, A190, A191, A192, A193,
  A194, A195, A196, A197, A198, A199, A200, A201, A202, A203,
  A204, A205, A206, A207, A208, A209, A210, A211, A212, A213,
  A214, A215, A216, A217, A218, A219, A220, A221, A222, A223,
  A224, A225, A226, A227, A228, A229, A230, A231, A232, A233,
  A234, A235, A236, A237, A238, A239, A240, A241, A242, A243,
  A244, A245, A246, A247, A248, A249, A250, A251, A252, A253,
  A254, A255, A256, A257, A258, A259, A260, A261, A262, A263,
  A264, A265, A266, A267, A268, A269, A270, A271, A272, A273,
  A274, A275, A276, A277, A278, A279, A280, A281, A282, A283,
  A284, A285, A286, A287, A288, A289, A290, A291, A292, A293,
  A294, A295, A296, A297, A298, A299, A300, A301, A302, A303,
  A304, A305, A306, A307, A308, A309, A310, A311, A312, A313,
  A314, A315, A316, A317, A318, A319, A320, A321, A322, A323,
  A324, A325, A326, A327, A328, A329, A330, A331, A332, A333,
  A334, A335, A336, A337, A338, A339, A340, A341, A342, A343,
  A344, A345, A346, A347, A348, A349, A350, A351, A352, A353,
  A354, A355, A356, A357, A358, A359, A360, A361, A362, A363,
  A364, A365, A366, A367, A368, A369, A370, A371, A372, A373,
  A374, A375, A376, A377, A378, A379, A380, A381, A382, A383,
  A384, A385, A386, A387, A388, A389, A390, A391, A392, A393,
  A394, A395, A396, A397, A398, A399, A400, A401, A402, A403,
  A404, A405, A406, A407, A408, A409, A410, A411, A412, A413,
  A414, A415, A416, A417, A418, A419, A420, A421, A422, A423,
  A424, A425, A426, A427, A428, A429, A430, A431, A432, A433,
  A434, A435, A436, A437, A438, A439, A440, A441, A442, A443,
  A444, A445, A446, A447, A448, A449, A450, A451, A452, A453,
  A454, A455, A456, A457, A458, A459, A460, A461, A462, A463,
  A464, A465, A466, A467, A468, A469, A470, A471, A472, A473,
  A474, A475, A476, A477, A478, A479, A480, A481, A482, A483,
  A484, A485, A486, A487, A488, A489, A490, A491, A492, A493,
  A494, A495, A496, A497, A498, A499, A500, A501, A502;
"""
    idd_obj = IddObject.load(group=group, object_lines=ori_text.splitlines())
    assert idd_obj._original_number_of_fields == 502

    assert str(idd_obj) == ori_text


def test_idd_object_name_field_index_with_reference():
    """name_field_index returns 0 for an object whose first field has \\reference."""
    group = "Thermal Zones and Surfaces"
    ori_text = """\
Zone,
       \\memo Provides a thermal zone description including parameters related to the
  A1 , \\field Name
       \\type alpha
       \\reference Zones
       \\reference ZoneNames
  N1 ; \\field Floor Area
       \\type real
       \\units m2
"""
    idd_obj = IddObject.load(group=group, object_lines=ori_text.splitlines())
    assert idd_obj.name_field_index() == 0


def test_idd_object_name_field_index_none_for_no_name():
    """name_field_index returns None for objects with no name field (e.g. SimulationControl)."""
    group = "Simulation Parameters"
    ori_text = """\
SimulationControl,
       \\unique-object
  A1 , \\field Do Zone Sizing Calculation
       \\type choice
       \\key Yes
       \\key No
       \\default No
  A2 ; \\field Do System Sizing Calculation
       \\type choice
       \\key Yes
       \\key No
       \\default No
"""
    idd_obj = IddObject.load(group=group, object_lines=ori_text.splitlines())
    assert idd_obj.name_field_index() is None


@pytest.mark.parametrize(
    "obsolete_line, replacement",
    [
        (r"\obsolete New=>deleted", "deleted"),
        (r"\obsolete New=>Some:Other:Object", "Some:Other:Object"),
        (r"\obsolete", ""),
    ],
)
def test_parse_idd_object_obsolete(obsolete_line, replacement) -> None:
    """Daylighting:DELight:ComplexFenestration: the replacement after \\obsolete must be kept, EnergyPlus' schema
    generator requires it ("expected string after /obsolete")"""
    ori_text = rf"""Daylighting:DELight:ComplexFenestration,
       \memo Used for DElight Complex Fenestration of all types
       {obsolete_line}
       \min-fields 1
  A1 ; \field Name
       \type alpha
"""
    idd_obj = IddObject.load(group="Daylighting", object_lines=ori_text.splitlines())
    assert idd_obj.properties.obsolete
    assert idd_obj.properties.obsolete_replacement == replacement
    assert f"       {obsolete_line}\n" in str(idd_obj)


def test_unnamed_compact_fields_written_back_compact() -> None:
    """GroundHeatTransfer:Basement:XFACE declares its fields without names: they must stay unnamed (no made-up
    '\\field N1'), otherwise the epJSON schema gets named fields it doesn't have."""
    ori_text = r"""GroundHeatTransfer:Basement:XFACE,
    \memo XFACE: X Direction cell face coordinates: m
       N1, N2, N3,  \note fields as indicated
       N4, N5;      \note fields as indicated
"""
    idd_obj = IddObject.load(group="Detailed Ground Heat Transfer", object_lines=ori_text.splitlines())
    assert len(idd_obj.fields) == 5
    text = str(idd_obj)
    assert "\\field" not in text
    assert "\\type" not in text
    assert_field_ids_consecutive(text, {"N": 5})
    assert text.rstrip().splitlines()[-1].split("\\")[0].strip().endswith("N5;")


def test_required_field_with_default_stays_required_in_idd() -> None:
    """SurfaceProperty:SurroundingSurfaces 'Surrounding Surface View Factor' is \\required-field with a \\default:
    the IDD must keep it required (it's the IDF side that treats a default as making it optional)."""
    ori_text = r"""Some:Object,
  A1 , \field Name
       \required-field
       \type alpha
  N1 ; \field View Factor
       \required-field
       \type real
       \default 0.5
"""
    idd_obj = IddObject.load(group="Test", object_lines=ori_text.splitlines())
    assert idd_obj.fields[1].properties.required
    assert str(idd_obj).count("\\required-field") == 2


def test_extensible_field_names_keep_the_group_number() -> None:
    """Extensible fields are named without the group number, but the IDD's name is written back, and the number is put
    back where it was for each group: "Vertex 3 X-coordinate", "DayType List 3"."""
    ori_text = r"""Some:Object,
       \extensible:2
  A1 , \field Name
       \type alpha
  N1 , \field Vertex 1 X-coordinate
       \begin-extensible
       \type real
  A2 ; \field DayType List 1
       \type alpha
"""
    idd_obj = IddObject.load(group="Test", object_lines=ori_text.splitlines())
    text = str(idd_obj)
    assert r"\field Vertex 1 X-coordinate" in text
    assert r"\field DayType List 1" in text
    assert text == ori_text


@pytest.mark.parametrize("idd_format", list(IddObjectFormat))
def test_parse_idd_object_format(idd_format) -> None:
    """\\format is spelled as in the IDD ("compactSchedule", "FluidProperty"...), and written back that way."""
    ori_text = rf"""Some:Object,
       \format {idd_format.value}
  A1 ; \field Name
       \type alpha
"""
    idd_obj = IddObject.load(group="Test", object_lines=ori_text.splitlines())
    assert idd_obj.properties.format == idd_format
    assert str(idd_obj) == ori_text


def test_parse_idd_object_format_is_case_insensitive() -> None:
    assert IddObjectFormat.parse("CompactSchedule") == IddObjectFormat.CompactSchedule
    assert IddObjectFormat.parse("SINGLELINE") == IddObjectFormat.SingleLine


@pytest.mark.parametrize("text", ["FluidProperties", "ViewFactors", "Banana"])
def test_parse_idd_object_unknown_format_is_an_error(text) -> None:
    """The IDD's documentation says "FluidProperties" and "ViewFactors", but the IDD uses "FluidProperty" and
    "ViewFactor": only those are accepted."""
    with pytest.raises(ValueError, match="Unknown \\\\format"):
        IddObject.load(group="Test", object_lines=["Some:Object,", f"  \\format {text}", "  A1 ; \\field Name"])


@pytest.mark.parametrize("junk", ["oops this is junk", "units m"])
def test_parse_idd_object_junk_line_before_next_field_is_an_error(junk) -> None:
    """A junk line at the end of a field is reported on that field, even if a valid field follows it."""
    object_lines = [
        "Some:Object,",
        "  N1 , \\field Height",
        "       \\type real",
        f"       {junk}",
        "  N2 ; \\field Width",
        "       \\type real",
    ]
    with pytest.raises(IddFieldParseError, match=f"^In 'Some:Object', field 'Height': Unexpected content.*'{junk}'"):
        IddObject.load(group="Test", object_lines=object_lines)


def test_parse_idd_object_begin_extensible_on_last_field() -> None:
    """A one-field extensible group declared last (nothing after it) was taken for a regular field: the last field of an
    object was added without checking its \\begin-extensible."""
    ori_text = r"""Schedule:Compact,
       \extensible:1
  A1 , \field Name
       \type alpha
  A2 ; \field Field 1
       \begin-extensible
       \type alpha
"""
    idd_obj = IddObject.load(group="Schedules", object_lines=ori_text.splitlines())
    assert [f.name for f in idd_obj.fields] == ["Name"]
    assert [f.name for f in idd_obj.extensible_fields] == ["Field"]
    assert str(idd_obj) == ori_text

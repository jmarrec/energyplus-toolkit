"""Tests for energyplus_parser.cpp.unit_test_file — block detection, C++ comments and IDF reformatting."""

import logging
from pathlib import Path

import pytest

from energyplus_parser.cpp.unit_test_file import (
    CppComment,
    DelimitedStringBlock,
    RawStringBlock,
    RegularCodeBlock,
    UnitTestFile,
)
from energyplus_parser.idd.idd_file import IddFile

RESOURCES = Path(__file__).parent.parent / "resources" / "cpp"
IDD_PATH = Path(__file__).parent.parent / "resources" / "V26-1-0-Energy+.idd"


@pytest.fixture(scope="session")
def ep_idd() -> IddFile:
    return IddFile.load(IDD_PATH)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse(text: str) -> list:
    return UnitTestFile(text).blocks


# ---------------------------------------------------------------------------
# Block detection — delimited_string
# ---------------------------------------------------------------------------


def test_detects_single_delimited_string_block():
    src = """\
int main() {
    auto s = delimited_string({
        "Zone,",
        "  Z1;",
    });
}
"""
    blocks = parse(src)
    assert len(blocks) == 3

    assert isinstance(blocks[0], RegularCodeBlock)
    assert blocks[0].content == """\
int main() {
    auto s = """

    assert isinstance(blocks[1], DelimitedStringBlock)
    assert blocks[1].content == """delimited_string({
        "Zone,",
        "  Z1;",
    })"""

    # The block ends at the '})' matching 'delimited_string({': what follows is part of the surrounding statement
    assert isinstance(blocks[2], RegularCodeBlock)
    assert blocks[2].content == """;
}
"""


def test_delimited_string_block_start_end():
    src = """\
before
    auto s = delimited_string({
        "Zone,",
    });
after
"""
    blocks = parse(src)
    ds = next(b for b in blocks if isinstance(b, DelimitedStringBlock))
    assert ds.start == 1  # 0-based: "    auto s = delimited_string({"
    assert ds.end == 3  # "    });"


def test_detects_two_delimited_string_blocks():
    src = """\
auto a = delimited_string({
    "Zone,",
    "  Z1;",
});
code();
auto b = delimited_string({
    "** Severe  ** something",
});
"""
    blocks = parse(src)
    ds_blocks = [b for b in blocks if isinstance(b, DelimitedStringBlock)]
    assert len(ds_blocks) == 2


def test_regular_code_surrounds_delimited_string():
    src = """\
before();
auto s = delimited_string({
    "Zone,",
});
after();
"""
    blocks = parse(src)
    assert isinstance(blocks[0], RegularCodeBlock)
    assert isinstance(blocks[1], DelimitedStringBlock)
    assert isinstance(blocks[2], RegularCodeBlock)


# ---------------------------------------------------------------------------
# Block detection — raw string
# ---------------------------------------------------------------------------


def test_detects_single_raw_string_block():
    src = """\
auto s = R"IDF(
    Zone,
      Z1;
    )IDF";
"""
    blocks = parse(src)
    assert sum(1 for b in blocks if isinstance(b, RawStringBlock)) == 1


def test_raw_string_block_start_end():
    src = """\
before
auto s = R"IDF(
    Zone,
    )IDF";
after
"""
    blocks = parse(src)
    rs = next(b for b in blocks if isinstance(b, RawStringBlock))
    assert rs.start == 1
    assert rs.end == 3


def test_raw_string_delimiter_captured():
    src = 'auto s = R"MYDELIM(\n    content\n    )MYDELIM";\n'
    blocks = parse(src)
    rs = next(b for b in blocks if isinstance(b, RawStringBlock))
    assert rs.delimiter == "MYDELIM"


def test_raw_string_empty_delimiter():
    src = 'auto s = R"(\n    content\n    )";\n'
    blocks = parse(src)
    rs = next(b for b in blocks if isinstance(b, RawStringBlock))
    assert rs.delimiter == ""


def test_detects_both_block_types():
    src = """\
auto a = delimited_string({
    "Zone,",
});
auto b = R"IDF(
    Zone,
    )IDF";
"""
    blocks = parse(src)
    assert sum(1 for b in blocks if isinstance(b, DelimitedStringBlock)) == 1
    assert sum(1 for b in blocks if isinstance(b, RawStringBlock)) == 1


# ---------------------------------------------------------------------------
# Block coverage: concatenating the raw block contents gives back the input text exactly.
# This only checks the block boundaries (no text lost, duplicated or reordered), no reformatting is involved.
# ---------------------------------------------------------------------------


def test_blocks_cover_whole_file():
    """Prefix/suffix code around delimited_string and R"IDF( blocks ends up in the surrounding regular blocks."""
    src = """\
before
auto s = delimited_string({
    "Zone,",
});
auto r = R"IDF(
    Zone,
    )IDF";
after
"""
    assert str(UnitTestFile(src)) == src


def test_blocks_cover_whole_file_regular_code_only():
    """A file with no IDF blocks is a single RegularCodeBlock."""
    src = "a\nb\nc\n"
    blocks = parse(src)
    assert len(blocks) == 1
    assert isinstance(blocks[0], RegularCodeBlock)
    assert str(UnitTestFile(src)) == src


# ---------------------------------------------------------------------------
# is_idf_block — DelimitedStringBlock
# ---------------------------------------------------------------------------


def test_delimited_string_idf_block_zone():
    src = 'auto s = delimited_string({\n    "Zone,",\n    "  Z1;",\n});\n'
    blocks = parse(src)
    ds = next(b for b in blocks if isinstance(b, DelimitedStringBlock))
    assert ds.is_idf_block() is True


def test_delimited_string_idf_block_schedule():
    src = 'auto s = delimited_string({\n' '    "Schedule:Compact,",\n' '    "  Name;",\n' '});\n'
    ds = next(b for b in parse(src) if isinstance(b, DelimitedStringBlock))
    assert ds.is_idf_block() is True


def test_delimited_string_error_string_is_not_idf():
    src = (
        'auto s = delimited_string({\n'
        '    "   ** Severe  ** something bad happened",\n'
        '    "   **   ~~~   ** more detail",\n'
        '});\n'
    )
    ds = next(b for b in parse(src) if isinstance(b, DelimitedStringBlock))
    assert ds.is_idf_block() is False


def test_delimited_string_error_string_with_semicolon_is_not_idf():
    """SolarShading.unit.cc: "DisplayExtraWarnings; for more details." looks like an object type followed by ';'."""
    src = """\
    std::string const error_string = delimited_string({
        "   ** Severe  ** Problem in interior solar distribution calculation (CHKBKS)",
        "   **   ~~~   **    Solar Distribution = FullInteriorExterior will not work in Zone=Zone1",
        "   **   ~~~   ** because one or more of vertices is in front of receiving surface=Floor",
        "   **   ~~~   ** (Dot Product indicator=   20.0000)",
        "   **   ~~~   ** Check surface geometry; if OK, use FullExterior instead. Use Output:Diagnostics,",
        "DisplayExtraWarnings; for more details.",
    });
"""
    ds = next(b for b in parse(src) if isinstance(b, DelimitedStringBlock))
    assert ds.is_idf_block() is False


@pytest.mark.parametrize("line", ["Some sentence, with a comma", "Note; see the docs", "Value is: 3, not 4"])
def test_delimited_string_prose_is_not_idf(line):
    """An object type has no spaces, and after a ';' only a '!' comment can follow."""
    src = f'auto s = delimited_string({{\n    "{line}",\n}});\n'
    ds = next(b for b in parse(src) if isinstance(b, DelimitedStringBlock))
    assert ds.is_idf_block() is False


@pytest.mark.parametrize(
    "line",
    [
        "Zone,",
        "  Zone,  ! A comment",
        "Timestep,4;",
        "Version,24.1;  !- Version Identifier",
        "Output:Diagnostics,DisplayExtraWarnings;",
        "AirTerminal:SingleDuct:VAV:Reheat,",
        "ShadowCalculation;",
    ],
)
def test_delimited_string_object_type_line_is_idf(line):
    src = f'auto s = delimited_string({{\n    "{line}",\n}});\n'
    ds = next(b for b in parse(src) if isinstance(b, DelimitedStringBlock))
    assert ds.is_idf_block() is True


def test_delimited_string_empty_strings_only_is_not_idf():
    src = 'auto s = delimited_string({\n    "",\n    "",\n});\n'
    ds = next(b for b in parse(src) if isinstance(b, DelimitedStringBlock))
    assert ds.is_idf_block() is False


# ---------------------------------------------------------------------------
# is_idf_block — RawStringBlock
# ---------------------------------------------------------------------------


def test_raw_string_idf_delimiter_is_idf_block():
    src = 'auto s = R"IDF(\n    Zone,\n    )IDF";\n'
    rs = next(b for b in parse(src) if isinstance(b, RawStringBlock))
    assert rs.is_idf_block() is True


def test_raw_string_other_delimiter_is_not_idf_block():
    src = 'auto s = R"JSON(\n    {}\n    )JSON";\n'
    rs = next(b for b in parse(src) if isinstance(b, RawStringBlock))
    assert rs.is_idf_block() is False


def test_raw_string_empty_delimiter_is_not_idf_block():
    src = 'auto s = R"(\n    content\n    )";\n'
    rs = next(b for b in parse(src) if isinstance(b, RawStringBlock))
    assert rs.is_idf_block() is False


def test_single_line_raw_string(ep_idd):
    """A single-line raw string is a RawStringBlock, but is never reformatted."""
    for src in ['std::string s = R"xxx(content)xxx"; // blablabla\n', 'std::string s = R"IDF(Zone,Z1;)IDF";\n']:
        blocks = parse(src)
        assert [type(b) for b in blocks] == [RegularCodeBlock, RawStringBlock, RegularCodeBlock]
        assert UnitTestFile(src).reformat(ep_idd) == src


def test_blocks_cover_whole_file_raw_string_with_prefix():
    """Content before R"del( on the same line does not get lost or duplicated."""
    src = 'auto s = R"IDF(\n    Zone,\n    )IDF";\n'
    assert str(UnitTestFile(src)) == src


def test_raw_string_prefix_goes_to_regular_block():
    src = '''auto s = R"IDF(
    Zone,
)IDF";
'''
    blocks = parse(src)
    reg = blocks[0]
    assert isinstance(reg, RegularCodeBlock)
    assert reg.content == "auto s = "


# ---------------------------------------------------------------------------
# C++ comments inside delimited_string
# ---------------------------------------------------------------------------


def parse_single_delimited(text: str) -> DelimitedStringBlock:
    ds_blocks = [b for b in parse(text) if isinstance(b, DelimitedStringBlock)]
    assert len(ds_blocks) == 1
    return ds_blocks[0]


def test_standalone_cpp_comment_between_objects():
    block = parse_single_delimited("""\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;",
        // A C++ comment
        "Zone,",
        "  Z2;",
    });
""")
    assert block.idf_content == "Zone,\nZ1;\nZone,\nZ2;"
    assert block.cpp_comments == [CppComment(text="// A C++ comment", idf_line_index=2, inline=False)]


def test_standalone_cpp_comment_inside_object():
    block = parse_single_delimited("""\
    std::string const idf_objects = delimited_string({
        "Zone,",
        // An in-object comment
        "  Z1;",
    });
""")
    assert block.idf_content == "Zone,\nZ1;"
    assert block.cpp_comments == [CppComment(text="// An in-object comment", idf_line_index=1, inline=False)]


def test_standalone_cpp_comment_after_last_string():
    block = parse_single_delimited("""\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;",
        // Trailing comment
    });
""")
    assert block.idf_content == "Zone,\nZ1;"
    assert block.cpp_comments == [CppComment(text="// Trailing comment", idf_line_index=2, inline=False)]


def test_inline_cpp_comment():
    block = parse_single_delimited("""\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;  !- Name", // An inline comment, with a "quote"
    });
""")
    assert block.idf_content == "Zone,\nZ1;  !- Name"
    assert block.cpp_comments == [
        CppComment(text='// An inline comment, with a "quote"', idf_line_index=1, inline=True)
    ]


def test_double_slash_inside_idf_string_is_not_a_cpp_comment():
    block = parse_single_delimited("""\
    std::string const idf_objects = delimited_string({
        "Schedule:File,",
        "  Sch1,                    !- Name",
        "  ,                        !- Schedule Type Limits Name",
        "  //server/share/sch.csv;  !- File Name",
    });
""")
    assert block.idf_content.splitlines()[-1] == "//server/share/sch.csv;  !- File Name"
    assert block.cpp_comments == []


def test_example_file_cpp_comments():
    f = UnitTestFile.from_path(RESOURCES / "Example.unit.cc")
    block = next(b for b in f.blocks if isinstance(b, DelimitedStringBlock) and b.is_idf_block())
    idf_lines = block.idf_content.splitlines()
    assert [(c.text, c.inline, idf_lines[c.idf_line_index]) for c in block.cpp_comments] == [
        ("// A C++ comment, that happens", False, "Zone,"),
        ("// An inline C++ comment, that happens", True, "0,                       !- Z Origin {m}"),
        ("// An in-object comment, that happens", False, "Zone3;"),
    ]


# ---------------------------------------------------------------------------
# Reformatting
# ---------------------------------------------------------------------------


def test_reformat_delimited_string(ep_idd):
    src = """\
    std::string const idf_objects = delimited_string({
        "  Zone,",
        "    Z1;",
        "",
    });
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_delimited_string_keeps_cpp_comments_in_place(ep_idd):
    """C++ comments follow the IDF value they were attached to, even when values get split onto separate lines."""
    src = """\
    std::string const idf_objects = delimited_string({
        // Before the object
        "Zone,Z1,",
        // Before the 2nd field
        "  90;", // Inline on the 2nd field
        // At the end
    });
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        // Before the object
        "Zone,",
        "  Z1,                      !- Name",
        // Before the 2nd field
        "  90.0;                    !- Direction of Relative North {deg}", // Inline on the 2nd field
        // At the end
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_raw_string_is_flush_left(ep_idd):
    src = """\
    std::string_view constexpr idf_objects = R"IDF(
        Zone,
          Z1;
    )IDF";
"""
    expected = """\
    std::string_view constexpr idf_objects = R"IDF(

Zone,
  Z1;                      !- Name

    )IDF";
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_leaves_non_idf_blocks_unchanged(ep_idd):
    src = """\
    std::string const error_string = delimited_string({
        "   ** Severe  ** Something went wrong",
    });
    auto r = R"JSON(
        {"a": 1}
    )JSON";
"""
    assert UnitTestFile(src).reformat(ep_idd) == src


def test_reformat_unknown_object_leaves_block_unchanged(ep_idd, caplog):
    """IdfFile skips unknown object types: reformatting would lose them, so the block is left as is."""
    src = """\
    std::string const idf_objects = delimited_string({
        "  Zone,",
        "    Z1;",
        "  NotAnObject,",
        "    Foo;",
    });
"""
    with caplog.at_level(logging.WARNING, logger="CppParser"):
        assert UnitTestFile(src).reformat(ep_idd) == src
    assert any("expected 2 IDF object(s) but parsed 1" in m for m in caplog.messages)


def test_reformat_unexpected_line_leaves_block_unchanged(ep_idd, caplog):
    src = """\
    std::string const idf_objects = delimited_string({
        "  Zone,",
        some_variable,
        "    Z1;",
    });
"""
    with caplog.at_level(logging.WARNING, logger="CppParser"):
        assert UnitTestFile(src).reformat(ep_idd) == src
    assert any("unexpected non-string line" in m for m in caplog.messages)


# ---------------------------------------------------------------------------
# Integration: example resource file
# ---------------------------------------------------------------------------


def test_example_file_reformat(ep_idd):
    """Reformatting the example unit test file gives the expected file."""
    f = UnitTestFile.from_path(RESOURCES / "Example.unit.cc")
    expected = (RESOURCES / "Example.unit.expected.cc").read_text(encoding="utf-8")
    assert f.reformat(ep_idd) == expected


def test_example_file_reformat_is_idempotent(ep_idd):
    """Reformatting the expected file again doesn't change it."""
    f = UnitTestFile.from_path(RESOURCES / "Example.unit.expected.cc")
    expected = (RESOURCES / "Example.unit.expected.cc").read_text(encoding="utf-8")
    assert f.reformat(ep_idd) == expected


def test_example_file_block_types():
    """The example unit test file should produce the expected block types."""
    f = UnitTestFile.from_path(RESOURCES / "Example.unit.cc")
    blocks = f.blocks
    ds_blocks = [b for b in blocks if isinstance(b, DelimitedStringBlock)]
    rs_blocks = [b for b in blocks if isinstance(b, RawStringBlock)]
    assert len(ds_blocks) == 2  # idf_objects + error_string
    assert len(rs_blocks) == 1  # R"IDF( block


def test_example_file_idf_block_detection():
    f = UnitTestFile.from_path(RESOURCES / "Example.unit.cc")
    ds_blocks = [b for b in f.blocks if isinstance(b, DelimitedStringBlock)]
    idf_ds = [b for b in ds_blocks if b.is_idf_block()]
    non_idf_ds = [b for b in ds_blocks if not b.is_idf_block()]
    assert len(idf_ds) == 1
    assert len(non_idf_ds) == 1


def test_example_file_raw_string_is_idf():
    f = UnitTestFile.from_path(RESOURCES / "Example.unit.cc")
    rs = next(b for b in f.blocks if isinstance(b, RawStringBlock))
    assert rs.is_idf_block() is True


def test_blocks_cover_whole_file_opener_on_its_own_indented_line():
    """Indentation before delimited_string({ / R"IDF( alone on their line is not lost."""
    src = """\
    std::string const error_string =
        delimited_string({"   ** Severe  ** Something",
                          "   **   ~~~   ** Else"});
    std::string const idf_objects =
        R"IDF(
            Zone,
              Z1;
        )IDF";
"""
    assert str(UnitTestFile(src)) == src


def test_example_file_blocks_cover_whole_file():
    """Splitting the example file into blocks does not lose, duplicate or reorder any text."""
    path = RESOURCES / "Example.unit.cc"
    original = path.read_text(encoding="utf-8")
    assert str(UnitTestFile(original)) == original


# ---------------------------------------------------------------------------
# Real-world cases, found by running on the EnergyPlus unit tests (tst/EnergyPlus/unit)
# ---------------------------------------------------------------------------


def delimited_blocks(text: str) -> list[DelimitedStringBlock]:
    return [b for b in parse(text) if isinstance(b, DelimitedStringBlock)]


def test_real_world_closer_double_paren(ep_idd):
    """IdfParser.unit.cc: ``test_object(delimited_string({ ... }));``"""
    src = """\
    std::string const test_object(delimited_string({
        "  Zone,",
        "    Z1;",
    }));

    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z2;                      !- Name",
    });
"""
    expected = """\
    std::string const test_object(delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    }));

    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z2;                      !- Name",
    });
"""
    assert len(delimited_blocks(src)) == 2
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_real_world_closer_process_idf(ep_idd):
    """``ASSERT_TRUE(process_idf(delimited_string({ ... })));``"""
    src = """\
    ASSERT_TRUE(process_idf(delimited_string({
        "  Zone,",
        "    Z1;",
    })));
"""
    expected = """\
    ASSERT_TRUE(process_idf(delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    })));
"""
    assert len(delimited_blocks(src)) == 1
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_real_world_closer_comma(ep_idd):
    """CurveManager.unit.cc: ``{delimited_string({ ... }), "message"}`` in an initializer list."""
    src = """\
    std::vector<std::pair<std::string, std::string>> errors = {
        {delimited_string({
             "  Zone,",
             "    Z1;",
         }),
         "Some error message"},
    };
"""
    expected = """\
    std::vector<std::pair<std::string, std::string>> errors = {
        {delimited_string({
             "Zone,",
             "  Z1;                      !- Name",
         }),
         "Some error message"},
    };
"""
    assert len(delimited_blocks(src)) == 1
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_real_world_non_idf_block_does_not_swallow_next_block(ep_idd):
    """EvaporativeFluidCoolers.unit.cc: an error string closing with ``})));`` must not run into the next block."""
    src = """\
    EXPECT_TRUE(compare_err_stream_substring(delimited_string({
        "   ** Severe  ** Autosizing error for evaporative fluid cooler object = BIG EVAPORATIVEFLUIDCOOLER",
    })));

    std::string const idf_objects = delimited_string({
        "  Zone,",
        "    Z1;",
    });
"""
    expected = """\
    EXPECT_TRUE(compare_err_stream_substring(delimited_string({
        "   ** Severe  ** Autosizing error for evaporative fluid cooler object = BIG EVAPORATIVEFLUIDCOOLER",
    })));

    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    });
"""
    blocks = delimited_blocks(src)
    assert len(blocks) == 2
    assert not blocks[0].is_idf_block()
    assert blocks[1].is_idf_block()
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_real_world_opener_in_cpp_comment(ep_idd):
    """DXCoils.unit.cc: a commented-out ``// EXPECT_TRUE( compare_eio_stream( delimited_string( {`` is not a block."""
    src = """\
    // EXPECT_TRUE( compare_eio_stream( delimited_string( {
    // 	"! <Component Sizing Information>, Component Type, Component Name, Input Field Description, Value",
    // 	" Component Sizing Information, Coil:Heating:DX:SingleSpeed, DX Heating coil, 0.00000" } ) ) );

    std::string const idf_objects = delimited_string({
        "  Zone,",
        "    Z1;",
    });
"""
    expected = """\
    // EXPECT_TRUE( compare_eio_stream( delimited_string( {
    // 	"! <Component Sizing Information>, Component Type, Component Name, Input Field Description, Value",
    // 	" Component Sizing Information, Coil:Heating:DX:SingleSpeed, DX Heating coil, 0.00000" } ) ) );

    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    });
"""
    assert len(delimited_blocks(src)) == 1
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_real_world_raw_string_split_for_msvc(ep_idd):
    """UnitarySystem.unit.cc: raw strings split in pieces for MSVC C2026 (string too long) must be left unchanged.

    Reformatting them as one would remove the split.
    """
    src = """\
    std::string_view constexpr idf_objects = R"IDF(
  Zone,
    Z1,                      !- Name
)IDF"
                                             R"IDF(
    0;                       !- Direction of Relative North {deg}
)IDF";
"""
    assert UnitTestFile(src).reformat(ep_idd) == src


def test_real_world_raw_string_split_for_msvc_in_comment(ep_idd):
    """UnitarySystem.unit.cc: same, with the split hidden at the end of a ``!-`` comment.

    The raw string ends at the first ``)IDF"``, which is inside what looks like an IDF comment.
    """
    src = """\
    std::string_view constexpr idf_objects = R"IDF(
  Zone,
    Z1,                      !- Name   " )IDF"
                                             R"IDF(" // split line for MSVC long string C2026
    0;                       !- Direction of Relative North {deg}
)IDF";
"""
    assert UnitTestFile(src).reformat(ep_idd) == src


def test_real_world_idf_line_split_in_two_cpp_strings(ep_idd):
    """AirflowNetworkHVAC.unit.cc: an IDF line split over two adjacent C++ strings is one IDF line, as in C++."""
    src = """\
    std::string const idf_objects = delimited_string({
        "  Zone,",
        "    Z1,                     !- Name "
        "{dimensionless}",
        "    0;",
    });
"""
    (block,) = delimited_blocks(src)
    assert block.idf_content == "Zone,\nZ1,                     !- Name {dimensionless}\n0;"
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1,                      !- Name",
        "  0.0;                     !- Direction of Relative North {deg}",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


@pytest.mark.parametrize(
    "src",
    [
        """\
    std::string_view constexpr idf_objects = R"IDF(
  Zone,
    Z1; // Not a C++ comment in a raw string
)IDF";
""",
        """\
    std::string const idf_objects = delimited_string({
        "  Zone,",
        "    Z1; some trailing text",
    });
""",
    ],
    ids=["raw-string", "delimited-string"],
)
def test_real_world_text_dropped_by_idf_file_leaves_block_unchanged(ep_idd, caplog, src):
    """Text that IdfFile would silently drop (after the last ',' or ';' of a line) must not be lost."""
    with caplog.at_level(logging.WARNING, logger="CppParser"):
        assert UnitTestFile(src).reformat(ep_idd) == src
    assert caplog.messages


def test_real_world_block_line_numbers():
    """Block start/end are the 0-based line numbers in the file, even after other blocks."""
    src = """\
    auto a = delimited_string({
        "Zone,",
        "  Z1;",
    });
    auto b = delimited_string({
        "Zone,",
        "  Z2;",
    });
"""
    first, second = delimited_blocks(src)
    assert (first.start, first.end) == (0, 3)
    assert (second.start, second.end) == (4, 7)


def test_real_world_integer_field_given_as_float(ep_idd):
    """SolarShading.unit.cc: "512.0, !- Pixel Counting Resolution" is an integer field given as a float: EnergyPlus
    accepts it, so the block is reformatted (with the value written as an integer) instead of being skipped."""
    src = """\
    std::string const idf_objects = delimited_string({
        "  Timestep,4.0;",
    });
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Timestep,4;",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


# ---------------------------------------------------------------------------
# Non-canonical delimited_string layouts: always rewritten in the canonical layout, which clang-format keeps one string
# per line thanks to the trailing comma.
# Expected outputs are what clang-format-19 gives with EnergyPlus' tst/.clang-format
# ---------------------------------------------------------------------------


def test_reformat_first_string_on_opener_line(ep_idd):
    """AirflowNetworkConditions.unit.cc: ``delimited_string({"Table:IndependentVariable,",`` and ``"  -0.56;"})``"""
    src = """\
    std::string const idf_objects = delimited_string({"  Zone,",
                                                      "    Z1;"});
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_brace_on_next_line(ep_idd):
    """AirflowNetworkConditions.unit.cc: ``delimited_string(`` then ``{"Material,",`` on the next line."""
    src = """\
    std::string const idf_objects = delimited_string(
        {"  Zone,",
         "    Z1;"});
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_last_string_on_closer_line(ep_idd):
    """AirflowNetworkHVAC.unit.cc: ``delimited_string({`` on its own line, but ``"...;"})`` on the last one."""
    src = """\
    ASSERT_TRUE(process_idf(delimited_string({
        "  Zone,",
        "    Z1;"})));
"""
    expected = """\
    ASSERT_TRUE(process_idf(delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    })));
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_non_canonical_nested_in_initializer_list(ep_idd):
    """In an initializer list, clang-format aligns '})' with 'delimited_string', and the strings 4 further."""
    src = """\
    std::vector<std::pair<std::string, std::string>> errors = {
        {delimited_string({"  Zone,",
                           "    Z1;"}),
         "Some error message"},
    };
"""
    expected = """\
    std::vector<std::pair<std::string, std::string>> errors = {
        {delimited_string({
             "Zone,",
             "  Z1;                      !- Name",
         }),
         "Some error message"},
    };
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


# ---------------------------------------------------------------------------
# clang-format changes must not be undone, or a pre-commit hook running us then clang-format would never be satisfied
# Inputs are what clang-format-19 gives with EnergyPlus' tst/.clang-format
# ---------------------------------------------------------------------------


def test_wrapped_inline_cpp_comment_is_a_continuation():
    """EMSManager.unit.cc: clang-format wraps a long inline comment on the next line, aligned under its '//'."""
    src = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name", // A long comment
                                              // that was wrapped
        // A standalone comment
    });
"""
    (block,) = delimited_blocks(src)
    assert block.cpp_comments == [
        CppComment(text="// A long comment", idf_line_index=1, inline=True, continuation=["// that was wrapped"]),
        CppComment(text="// A standalone comment", idf_line_index=2, inline=False),
    ]


def test_reformat_keeps_wrapped_inline_cpp_comment_with_its_line(ep_idd):
    """ZoneTempPredictorCorrector.unit.cc: the continuation of a wrapped comment stays with it, before a blank line."""
    src = """\
    std::string const idf_objects = delimited_string({
        "  Zone,Z1;", // This is an error because this object does NOT exist (cause
                      // of defect)
        "",
        "Zone,Z2;",
    });
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name", // This is an error because this object does NOT exist (cause
                                              // of defect)

        "Zone,",
        "  Z2;                      !- Name",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


@pytest.mark.parametrize(
    "src",
    [
        # StandardRatings.unit.cc: trailing comments aligned
        """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1,                      !- Name",                       // Short
        "  90.0;                    !- Direction of Relative North {deg}", // Longer
    });
""",
        # EMSManager.unit.cc: long trailing comment wrapped, at different places
        """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name", // A long comment that was
                                              // wrapped by clang-format
    });
""",
        # HVACVariableRefrigerantFlow.unit.cc: long string literal split in adjacent ones
        """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1,                      !- Name",
        "  90.0;                    !- Direction of "
        "Relative North {deg}",
    });
""",
    ],
    ids=["aligned-comments", "wrapped-comment", "split-literal"],
)
def test_reformat_keeps_clang_format_changes(ep_idd, src, caplog):
    """The block is reformatted (no warning), but the output only differs by what clang-format changes: kept as is."""
    with caplog.at_level(logging.WARNING, logger="CppParser"):
        assert UnitTestFile(src).reformat(ep_idd) == src
    assert not caplog.messages


def test_reformat_split_literal_with_idf_change(ep_idd):
    """HVACVariableRefrigerantFlow.unit.cc: a string split by clang-format is still reformatted when the IDF changes.
    It's written back on one line, clang-format splits it again."""
    src = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1,                      !- Name",
        "  90;                      !- Direction of "
        "Relative North {deg}",
    });
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1,                      !- Name",
        "  90.0;                    !- Direction of Relative North {deg}",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_empty_string_line_is_not_kept(ep_idd):
    """A ``"",`` line between objects is a change, not a clang-format one: it's written as a real blank line."""
    src = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
        "",
        "Zone,",
        "  Z2;                      !- Name",
    });
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",

        "Zone,",
        "  Z2;                      !- Name",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected


def test_reformat_still_rewrites_line_structure(ep_idd):
    """Only whitespace is ignored: an already formatted IDF in a non-canonical layout is still rewritten."""
    src = """\
    std::string const idf_objects = delimited_string({"Zone,",
                                                      "  Z1;                      !- Name",
    });
"""
    expected = """\
    std::string const idf_objects = delimited_string({
        "Zone,",
        "  Z1;                      !- Name",
    });
"""
    assert UnitTestFile(src).reformat(ep_idd) == expected

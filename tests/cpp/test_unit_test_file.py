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
    });"""

    assert isinstance(blocks[2], RegularCodeBlock)
    assert blocks[2].content == """
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


def test_single_line_raw_string_is_regular_code():
    """A single-line raw string is not split into a RawStringBlock."""
    src = 'std::string idf_objects = R"xxx(content)xxx"; // blablabla\n'
    blocks = parse(src)
    assert all(isinstance(b, RegularCodeBlock) for b in blocks)


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

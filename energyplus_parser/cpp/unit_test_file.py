"""Parse C++ EnergyPlus unit test files into typed blocks, and reformat the IDF content they embed.

Two block types may contain IDF content:

  delimited_string({
    "ObjectType,",
    "  Field,  !- Name",
    ...
  });

  R"IDF(
    ObjectType,
      Field,  !- Name
  )IDF"
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from energyplus_parser.idd.idd_constants import COMMENT_ONLY_OBJECT_NAME
from energyplus_parser.idd.idd_file import IddFile
from energyplus_parser.idf.idf_file import IdfFile

LOG = logging.getLogger("CppParser")

# ---------------------------------------------------------------------------
# Regexes
# ---------------------------------------------------------------------------

# C++ IDF string line, with an optional trailing inline C++ comment.
#   '    "    Zone,               !- Name",  // optional'
#   '    "",  '
# Group 1: leading whitespace + opening quote
# Group 2: IDF content between the quotes
# Group 3: closing quote + optional comma + whitespace
# Group 4: optional trailing inline C++ comment, starting at '//' (None if absent)
CPP_STRING_RE = re.compile(r'^(\s*")(.*?)("[\s,]*)(?:\s*(//.*))?$')

# Matches a standalone C++ comment line (// ...).
CPP_COMMENT_LINE_RE = re.compile(r'^\s*//')

# Detects delimited_string({ anywhere on a line.
DELIMITED_OPEN_RE = re.compile(r'delimited_string\s*\(\s*\{')

# Matches the closing });  of a delimited_string block.
DELIMITED_CLOSE_RE = re.compile(r'\}\s*\)\s*;')

# Raw string literals: https://en.cppreference.com/cpp/language/string_literal
# R"d-char-seq(r-char-seq)d-char-seq"
# d-char-seq: up to 16 chars, no whitespace or '('
# Captures the d-char-seq in group 1.
# TODO: warn if d-char-seq isn't "IDF" but content looks like IDF, or vice versa.
RAW_OPEN_RE = re.compile(r'R"([^\s(]{0,16})\(')

# Matches the closing )d-char-seq" of a raw string literal (possibly with trailing ;).
# Captures the d-char-seq in group 1.
RAW_CLOSE_RE = re.compile(r'\)([^\s)]{0,16})"\s*;')

# IDF object-type line heuristic: bare identifier (with optional colons/spaces)
# followed by ',' or ';'. Rules out error strings like "** Severe **...".
_IDF_OBJECT_TYPE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9: ]*[,;]')


# ---------------------------------------------------------------------------
# Block classes
# ---------------------------------------------------------------------------


def extract_repr(content: str) -> str:
    lines = content.splitlines()
    if not lines:
        return ""
    if len(lines) == 1:
        return lines[0]
    start_line = 0
    while start_line < len(lines) and not lines[start_line].strip():
        start_line += 1
    if start_line == len(lines):
        return ""
    end_line = len(lines) - 1
    while end_line > start_line and not lines[end_line].strip():
        end_line -= 1
    if end_line == start_line:
        return lines[start_line]
    return f"{lines[start_line]}\n  [...]\n{lines[end_line]}"


@dataclass
class CppComment:
    """A C++ comment found inside a delimited_string block, anchored to a line of the extracted IDF content.

    - Standalone (inline=False): the comment sits on its own line, *before* IDF line ``idf_line_index``.
      ``idf_line_index`` may be equal to the number of IDF lines if the comment is after the last string.
    - Inline (inline=True): the comment trails the string on IDF line ``idf_line_index``.
    """

    text: str  # includes the leading '//'
    idf_line_index: int
    inline: bool


@dataclass(frozen=True)
class _IdfValue:
    """Where an IDF value (object type or field) sits in a list of IDF lines.

    ``index`` is 0 for the object type, 1 for the first field, etc.
    """

    obj: int
    index: int
    start_line: int  # line of its first non-blank character (or of its separator, if the value is empty)
    end_line: int  # line of its ',' or ';' separator


def _locate_idf_values(idf_lines: list[str]) -> list[_IdfValue]:
    """Locate every IDF value by line, ignoring ``!`` comments."""
    values: list[_IdfValue] = []
    obj = index = 0
    start: int | None = None
    for n, line in enumerate(idf_lines):
        for ch in line.split("!", 1)[0]:
            if ch in ",;":
                values.append(_IdfValue(obj=obj, index=index, start_line=n if start is None else start, end_line=n))
                start = None
                if ch == ";":
                    obj += 1
                    index = 0
                else:
                    index += 1
            elif start is None and not ch.isspace():
                start = n
    return values


def _count_idf_objects(idf_text: str) -> int:
    """Count IDF objects by counting ';' outside of ``!`` comments."""
    return sum(line.split("!", 1)[0].count(";") for line in idf_text.splitlines())


def _format_idf(idf_text: str, idd: IddFile, where: str) -> list[str] | None:
    """Parse and reformat IDF text, returning the formatted lines without leading/trailing blank lines.

    Returns None (and logs a warning) if the text can't be reformatted safely, eg if an object would be lost because
    its type isn't in the IDD.
    """
    expected_count = _count_idf_objects(idf_text)
    if expected_count == 0:
        return None
    try:
        idf = IdfFile.loads(idf_text, idd)
    except Exception as exc:
        LOG.warning(f"{where}: failed to parse IDF ({exc}) — leaving unchanged")
        return None
    parsed_count = sum(1 for obj in idf.objects if obj.idd_object.name != COMMENT_ONLY_OBJECT_NAME)
    if parsed_count != expected_count:
        LOG.warning(
            f"{where}: expected {expected_count} IDF object(s) but parsed {parsed_count} (check IDD version)"
            " — leaving unchanged"
        )
        return None
    lines = str(idf).splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


class Block(ABC):
    """A contiguous span of lines from a C++ unit test file."""

    def __init__(self, content: str, start: int, end: int) -> None:
        self.content = content  # full raw text including any delimiters
        self.start = start  # 0-based index of first line
        self.end = end  # 0-based index of last line (inclusive)

    @abstractmethod
    def is_idf_block(self) -> bool:
        """Return True if this block contains (or is likely to contain) IDF objects."""

    def __str__(self) -> str:
        return self.content

    def reformat(self, idd: IddFile) -> str:
        """Return the block's text with any IDF content reformatted. Non-IDF blocks are returned unchanged."""
        return self.content

    @abstractmethod
    def __repr__(self) -> str:
        pass


class RegularCodeBlock(Block):
    """Plain C++ code — not an IDF block."""

    def is_idf_block(self) -> bool:
        return False

    def __repr__(self) -> str:
        return f"RegularCodeBlock(lines {self.start}-{self.end}```\n{extract_repr(self.content)}\n```)"


class PotentialIdfBlock(Block, ABC):
    """A block that may contain IDF content."""

    def __init__(self, content: str, start: int, end: int) -> None:
        super().__init__(content, start, end)
        self.idf_content: str | None = None
        self._is_idf_block: bool = self._detect_idf()
        if self._is_idf_block:
            self.idf_content = self._parse_idf_content()

    @abstractmethod
    def _detect_idf(self) -> bool:
        """Return True if this block contains IDF content."""

    def is_idf_block(self) -> bool:
        return self._is_idf_block

    @abstractmethod
    def _parse_idf_content(self) -> str | None:
        """Return the IDF content, or None if it can't be extracted (the block is then left unchanged)."""

    def reformat(self, idd: IddFile) -> str:
        if self.idf_content is None:
            return self.content
        reformatted = self._reformat(idd)
        return self.content if reformatted is None else reformatted

    @abstractmethod
    def _reformat(self, idd: IddFile) -> str | None:
        """Return the reformatted block text, or None to leave it unchanged."""

    def _where(self) -> str:
        return f"{type(self).__name__} at line {self.start + 1}"


class DelimitedStringBlock(PotentialIdfBlock):
    """A ``delimited_string({ ... });`` block."""

    def __init__(self, content: str, start: int, end: int) -> None:
        # set before super().__init__ calls _parse_idf_content
        self.cpp_comments: list[CppComment] = []
        self.indent = ""  # indentation of the first quoted string line
        super().__init__(content, start, end)

    def _detect_idf(self) -> bool:
        """Scan quoted string lines for at least one IDF object-type line."""
        for line in self.content.splitlines():
            m = CPP_STRING_RE.match(line.rstrip("\n\r"))
            if m:
                idf_content = m.group(2).strip()
                if idf_content and _IDF_OBJECT_TYPE_RE.match(idf_content):
                    return True
        return False

    def __repr__(self) -> str:
        return f"DelimitedStringBlock(lines {self.start}-{self.end}, is_idf={self._is_idf_block})"

    def _parse_idf_content(self) -> str | None:
        """Extract the IDF content from the quoted lines, concatenating with newlines.

        Blank lines (and empty "" strings) become blank IDF lines, as they separate IDF comments from objects.
        C++ comments (standalone or inline) are not part of the IDF content, they are recorded in ``cpp_comments``.
        """
        m_open = DELIMITED_OPEN_RE.match(self.content)
        m_close = DELIMITED_CLOSE_RE.search(self.content)
        if m_open is None or m_close is None:
            LOG.warning(f"{self._where()}: malformed delimited_string block — leaving unchanged")
            return None

        idf_lines: list[str] = []
        inner_lines = self.content[m_open.end() : m_close.start()].splitlines()
        # Drop what's left of the 'delimited_string({' line and the indentation before '});', when blank
        if inner_lines and not inner_lines[0].strip():
            inner_lines.pop(0)
        if inner_lines and not inner_lines[-1].strip():
            inner_lines.pop()

        found_string = False
        for line in inner_lines:
            m = CPP_STRING_RE.match(line.rstrip("\n\r"))
            if m:
                if not found_string:
                    self.indent = m.group(1)[:-1]
                    found_string = True
                idf_content = m.group(2).strip()
                idf_lines.append(idf_content)
                if m.group(4):
                    self.cpp_comments.append(
                        CppComment(text=m.group(4).rstrip(), idf_line_index=len(idf_lines) - 1, inline=True)
                    )
            elif CPP_COMMENT_LINE_RE.match(line):
                self.cpp_comments.append(CppComment(text=line.strip(), idf_line_index=len(idf_lines), inline=False))
            elif not line.strip():
                idf_lines.append("")
            else:
                LOG.warning(f"{self._where()}: unexpected non-string line '{line.strip()}' — leaving unchanged")
                return None
        return "\n".join(idf_lines)

    def _reformat(self, idd: IddFile) -> str | None:
        assert self.idf_content is not None
        lines = self.content.splitlines(keepends=True)
        # Only handle the canonical layout, with delimited_string({ and }); on their own lines
        if len(lines) < 2 or not DELIMITED_OPEN_RE.fullmatch(lines[0].strip()) or lines[-1].strip() != "});":
            return None
        if '"' in self.idf_content or "\\" in self.idf_content:
            return None  # would need C++ escaping
        eol = "\r\n" if lines[0].endswith("\r\n") else "\n"

        formatted = _format_idf(self.idf_content, idd, self._where())
        if formatted is None:
            return None

        # Anchor C++ comments to an IDF value (object, field index), and find that value in the formatted lines
        src_values = _locate_idf_values(self.idf_content.splitlines())
        out_values = {(v.obj, v.index): v for v in _locate_idf_values(formatted)}
        before: dict[int, list[str]] = defaultdict(list)  # formatted line index -> comments placed before it
        inline: dict[int, list[str]] = defaultdict(list)  # formatted line index -> comments trailing it
        trailing: list[str] = []
        for c in self.cpp_comments:
            if c.inline:
                anchor = next((v for v in reversed(src_values) if v.end_line == c.idf_line_index), None)
                if anchor is not None:
                    if (anchor.obj, anchor.index) not in out_values:
                        LOG.warning(f"{self._where()}: could not place C++ comment '{c.text}' — leaving unchanged")
                        return None
                    inline[out_values[(anchor.obj, anchor.index)].end_line].append(c.text)
                    continue
            # Standalone (or inline on a line with no IDF value, eg an IDF comment): place before the next value
            anchor = next((v for v in src_values if v.start_line >= c.idf_line_index), None)
            if anchor is None:
                trailing.append(c.text)
            elif (anchor.obj, anchor.index) not in out_values:
                LOG.warning(f"{self._where()}: could not place C++ comment '{c.text}' — leaving unchanged")
                return None
            else:
                before[out_values[(anchor.obj, anchor.index)].start_line].append(c.text)

        body: list[str] = []
        for n, idf_line in enumerate(formatted):
            body.extend(f"{self.indent}{text}{eol}" for text in before[n])
            if not idf_line:
                body.append(eol)
                continue
            cpp_line = f'{self.indent}"{idf_line}",'
            if inline[n]:
                cpp_line += " " + " ".join(inline[n])
            body.append(f"{cpp_line}{eol}")
        body.extend(f"{self.indent}{text}{eol}" for text in trailing)

        return lines[0] + "".join(body) + lines[-1]


class RawStringBlock(PotentialIdfBlock):
    """A ``R"delimiter(...)delimiter"`` raw string literal block."""

    def __init__(self, content: str, start: int, end: int, delimiter: str) -> None:
        self.delimiter = delimiter  # set before super().__init__ calls _detect_idf
        super().__init__(content, start, end)

    def _detect_idf(self) -> bool:
        return self.delimiter == "IDF"

    def __repr__(self) -> str:
        return (
            f"RawStringBlock(lines {self.start}-{self.end}, is_idf={self._is_idf_block}\n"
            f'R"{self.delimiter}(\n{extract_repr(self.content)}\n){self.delimiter})"'
        )

    def _parse_idf_content(self) -> str | None:
        """Return the raw string's content, between ``R"IDF(`` and ``)IDF"``."""
        m_open = RAW_OPEN_RE.match(self.content)
        close_idx = self.content.rfind(f'){self.delimiter}"')
        if m_open is None or close_idx < m_open.end():
            LOG.warning(f"{self._where()}: malformed raw string block — leaving unchanged")
            return None
        return self.content[m_open.end() : close_idx]

    def _reformat(self, idd: IddFile) -> str | None:
        """Reformat the IDF flush left, with a blank line after R"IDF( and before the (untouched) )IDF" line."""
        assert self.idf_content is not None
        lines = self.content.splitlines(keepends=True)
        # Only handle the canonical layout, with R"IDF( ending its line and )IDF" starting its line
        if len(lines) < 2 or lines[0].strip() != f'R"{self.delimiter}(' or not lines[-1].lstrip().startswith(")"):
            return None
        eol = "\r\n" if lines[0].endswith("\r\n") else "\n"

        formatted = _format_idf(self.idf_content, idd, self._where())
        if formatted is None:
            return None

        body = "".join(f"{line}{eol}" if line else eol for line in formatted)
        return f"{lines[0]}{eol}{body}{eol}{lines[-1]}"


# ---------------------------------------------------------------------------
# UnitTestFile
# ---------------------------------------------------------------------------


class UnitTestFile:
    """A parsed C++ EnergyPlus unit test file, decomposed into typed blocks."""

    def __init__(self, content: str) -> None:
        self.content = content
        self._blocks: list[Block] = []
        self._parse()

    @staticmethod
    def from_path(path: Path | str) -> "UnitTestFile":
        return UnitTestFile(content=Path(path).read_text(encoding="utf-8", errors="replace"))

    @property
    def blocks(self) -> list[Block]:
        return list(self._blocks)

    def __str__(self) -> str:
        return "".join(str(b) for b in self._blocks)

    def reformat(self, idd: IddFile) -> str:
        """Return the file's text with the IDF content of every IDF block reformatted."""
        return "".join(b.reformat(idd) for b in self._blocks)

    def _parse(self) -> None:
        lines = self.content.splitlines(keepends=True)
        n = len(lines)
        i = 0
        regular_start = 0

        def flush_regular(up_to: int) -> None:
            if up_to > regular_start:
                self._blocks.append(
                    RegularCodeBlock(
                        content="".join(lines[regular_start:up_to]),
                        start=regular_start,
                        end=up_to - 1,
                    )
                )

        while i < n:
            stripped = lines[i].rstrip("\n\r")

            # ---- delimited_string({ ----
            if m_ds := DELIMITED_OPEN_RE.search(stripped):
                open_prefix = lines[i][: m_ds.start()]
                open_suffix = lines[i][m_ds.start() :]  # from delimited_string({ onward

                if open_prefix:
                    self._blocks.append(
                        RegularCodeBlock(
                            content="".join(lines[regular_start:i]) + open_prefix,
                            start=regular_start,
                            end=i,
                        )
                    )
                else:
                    flush_regular(i)

                j = i + 1
                raw_parts = [open_suffix]
                close_suffix = ""
                while j < n:
                    if m_close := DELIMITED_CLOSE_RE.search(lines[j]):
                        raw_parts.append(lines[j][: m_close.end()])
                        close_suffix = lines[j][m_close.end() :]
                        j += 1
                        break
                    raw_parts.append(lines[j])
                    j += 1
                self._blocks.append(
                    DelimitedStringBlock(
                        content="".join(raw_parts),
                        start=i,
                        end=j - 1,
                    )
                )
                i = j
                regular_start = i
                if close_suffix:
                    lines.insert(i, close_suffix)
                    n = len(lines)
                continue

            # ---- R"delimiter( ----
            m = RAW_OPEN_RE.search(stripped)
            if m:
                delimiter = m.group(1)
                close_re = re.compile(r'\)' + re.escape(delimiter) + r'"\s*;')

                # Single-line raw string: open and close on the same line.
                # Not reformattable; let it fall through as regular code.
                if close_re.search(stripped[m.end() :]):
                    i += 1
                    continue

                # Multi-line raw string.
                # Split the opening line: prefix before R"del( → regular code,
                # the rest (from R"del( onward) → start of raw string content.
                open_prefix = lines[i][: m.start()]
                open_suffix = lines[i][m.start() :]  # includes trailing \n

                if open_prefix:
                    self._blocks.append(
                        RegularCodeBlock(
                            content="".join(lines[regular_start:i]) + open_prefix,
                            start=regular_start,
                            end=i,
                        )
                    )
                else:
                    flush_regular(i)

                # Collect inner lines + closing line.
                raw_parts = [open_suffix]
                j = i + 1
                close_suffix = ""
                while j < n:
                    m_close = close_re.search(lines[j].rstrip("\n\r"))
                    if m_close:
                        # Everything up to and including the close marker stays in the block.
                        close_suffix = lines[j][m_close.end() :]
                        raw_parts.append(lines[j][: m_close.end()])
                        j += 1
                        break
                    raw_parts.append(lines[j])
                    j += 1

                self._blocks.append(
                    RawStringBlock(
                        content="".join(raw_parts),
                        start=i,
                        end=j - 1,
                        delimiter=delimiter,
                    )
                )
                i = j
                regular_start = i
                # Suffix after the closing marker (e.g. " // comment\n") becomes
                # the start of the next regular block.
                if close_suffix:
                    lines.insert(i, close_suffix)
                    n = len(lines)
                continue

            i += 1

        flush_regular(n)

    def __repr__(self) -> str:
        return f"UnitTestFile with {len(self._blocks)} blocks:\n" + "\n".join(f"  {b!r}" for b in self._blocks)

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

# Matches delimited_string({ (the block ends at the matching '})').
DELIMITED_OPEN_RE = re.compile(r'delimited_string\s*\(\s*\{')

# Raw string literals: https://en.cppreference.com/cpp/language/string_literal
# R"d-char-seq(r-char-seq)d-char-seq"
# d-char-seq: up to 16 chars, no whitespace or '('
# Captures the d-char-seq in group 1. The raw string ends at the first )d-char-seq".
# TODO: warn if d-char-seq isn't "IDF" but content looks like IDF, or vice versa.
RAW_OPEN_RE = re.compile(r'R"([^\s(]{0,16})\(')

# What the C++ scanner has to look at: comments, string/char literals, and block openers
_CPP_SCAN_RE = re.compile(r'//|/\*|R"|"|\'|delimited_string')

# IDF object-type line heuristic: an object type (letters, digits, ':' and '-', no spaces, as in the IDD) followed by
# ',' or by ';' and nothing else but a '!' comment.
# Rules out error strings like "** Severe **..." or "DisplayExtraWarnings; for more details."
_IDF_OBJECT_TYPE_RE = re.compile(r'^[A-Za-z][A-Za-z0-9:-]*\s*(,|;\s*(!.*)?$)')


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
    for line in idf_text.splitlines():
        # IdfFile only keeps what's before a ',' or ';' (and '!' comments): anything else would be silently lost
        data = line.split("!", 1)[0]
        if data[max(data.rfind(","), data.rfind(";")) + 1 :].strip():
            LOG.warning(f"{where}: text outside of an IDF field would be lost ({line.strip()!r}) — leaving unchanged")
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
    """A ``delimited_string({ ... })`` block.

    It is always written back in the canonical layout: ``delimited_string({`` and ``})`` on their own lines, and one
    ``"...",`` per line. Thanks to the trailing comma, clang-format keeps it that way.
    """

    def __init__(self, content: str, start: int, end: int, closer_indent: str = "") -> None:
        # set before super().__init__ calls _parse_idf_content
        self.cpp_comments: list[CppComment] = []
        self.indent = ""  # indentation of the first quoted string line
        # Where clang-format puts '})' when the block is rewritten: see UnitTestFile._closer_indent
        self.closer_indent = closer_indent
        super().__init__(content, start, end)

    def _inner_lines(self) -> list[str] | None:
        """The lines between ``delimited_string({`` and the closing ``}``, or None if the block is malformed.

        What's left of the opener line and the indentation before ``}`` are dropped when blank.
        """
        m_open = DELIMITED_OPEN_RE.match(self.content)
        close_idx = self.content.rfind("}")
        if m_open is None or close_idx < m_open.end():
            return None
        inner_lines = self.content[m_open.end() : close_idx].splitlines()
        if inner_lines and not inner_lines[0].strip():
            inner_lines.pop(0)
        if inner_lines and not inner_lines[-1].strip():
            inner_lines.pop()
        return inner_lines

    def _detect_idf(self) -> bool:
        """Scan quoted string lines for at least one IDF object-type line."""
        for line in self._inner_lines() or []:
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
        inner_lines = self._inner_lines()
        if inner_lines is None:
            LOG.warning(f"{self._where()}: malformed delimited_string block — leaving unchanged")
            return None

        idf_lines: list[str] = []

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
        if '"' in self.idf_content or "\\" in self.idf_content:
            return None  # would need C++ escaping
        eol = "\r\n" if lines[0].endswith("\r\n") else "\n"

        # Already in the canonical layout: keep its opener, closer and indentation. Otherwise (strings on the opener or
        # closer line, or '{' on the line after 'delimited_string('), rewrite it with clang-format's indentation.
        if (
            len(lines) > 1
            and DELIMITED_OPEN_RE.fullmatch(lines[0].strip())
            and re.fullmatch(r"\}\s*\)", lines[-1].strip())
        ):
            opener, indent, closer = lines[0], self.indent, lines[-1]
        else:
            opener, indent, closer = (
                f"delimited_string({{{eol}",
                self.closer_indent + "    ",
                f"{self.closer_indent}}})",
            )

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
            body.extend(f"{indent}{text}{eol}" for text in before[n])
            if not idf_line:
                body.append(eol)
                continue
            cpp_line = f'{indent}"{idf_line}",'
            if inline[n]:
                cpp_line += " " + " ".join(inline[n])
            body.append(f"{cpp_line}{eol}")
        body.extend(f"{indent}{text}{eol}" for text in trailing)

        return opener + "".join(body) + closer


class RawStringBlock(PotentialIdfBlock):
    """A ``R"delimiter(...)delimiter"`` raw string literal block."""

    def __init__(self, content: str, start: int, end: int, delimiter: str) -> None:
        self.delimiter = delimiter  # set before super().__init__ calls _detect_idf
        # Set by UnitTestFile when this is one piece of adjacent raw strings ("R"IDF(...)IDF" R"IDF(...)IDF""), which
        # is how long strings are split to avoid MSVC error C2026 (string too big). Those are never reformatted.
        self.concatenated = False
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
        if self.concatenated:
            LOG.warning(f"{self._where()}: raw string split in several pieces (MSVC C2026) — leaving unchanged")
            return None
        lines = self.content.splitlines(keepends=True)
        # Only handle the canonical layout, with R"IDF( ending its line and )IDF" on its own line
        if len(lines) < 2 or lines[0].strip() != f'R"{self.delimiter}(' or lines[-1].strip() != f'){self.delimiter}"':
            return None
        eol = "\r\n" if lines[0].endswith("\r\n") else "\n"

        formatted = _format_idf(self.idf_content, idd, self._where())
        if formatted is None:
            return None

        body = "".join(f"{line}{eol}" if line else eol for line in formatted)
        return f"{lines[0]}{eol}{body}{eol}{lines[-1]}"


# ---------------------------------------------------------------------------
# C++ scanning helpers
# ---------------------------------------------------------------------------


def _skip_quoted(text: str, pos: int) -> int:
    """Return the position after the string or char literal starting at ``pos`` (``"`` or ``'``)."""
    quote = text[pos]
    if quote == "'" and pos > 0 and text[pos - 1].isalnum():
        return pos + 1  # digit separator, eg 1'000'000
    i = pos + 1
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
        elif c == quote:
            return i + 1
        elif c == "\n":
            return i  # unterminated
        else:
            i += 1
    return i


def _find_delimited_close(text: str, pos: int) -> int | None:
    """Return the position after the ``})`` closing a ``delimited_string({`` whose ``{`` ends at ``pos``.

    Skips string literals and comments. Returns None if there's no matching ``})``.
    """
    depth = 0
    i = pos
    while i < len(text):
        if text.startswith("//", i):
            newline = text.find("\n", i)
            i = len(text) if newline == -1 else newline
        elif text.startswith("/*", i):
            close = text.find("*/", i + 2)
            i = len(text) if close == -1 else close + 2
        elif text[i] in "\"'":
            i = _skip_quoted(text, i)
        elif text[i] == "{":
            depth += 1
            i += 1
        elif text[i] == "}":
            if depth > 0:
                depth -= 1
                i += 1
                continue
            m = re.compile(r"\}\s*\)").match(text, i)
            return None if m is None else m.end()
        else:
            i += 1
    return None


def _strip_cpp_comments(code: str) -> str:
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", code, flags=re.DOTALL)


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
        """Split the file into blocks, scanning it like a C++ lexer would.

        Comments and string literals are skipped, so a ``delimited_string({`` inside a ``// comment`` or a ``})`` inside
        a string isn't taken for a block boundary.
        """
        text = self.content
        regular_start = 0
        pos = 0
        while (m := _CPP_SCAN_RE.search(text, pos)) is not None:
            token, pos = m.group(), m.start()
            if token == "//":
                newline = text.find("\n", pos)
                pos = len(text) if newline == -1 else newline
            elif token == "/*":
                close = text.find("*/", pos + 2)
                pos = len(text) if close == -1 else close + 2
            elif token == '"' or token == "'":
                pos = _skip_quoted(text, pos)
            elif token == 'R"':
                m_raw = RAW_OPEN_RE.match(text, pos)
                close = -1 if m_raw is None else text.find(f'){m_raw.group(1)}"', m_raw.end())
                if m_raw is None or close == -1:
                    pos = _skip_quoted(text, pos + 1)  # not a valid raw string: treat as a regular string
                    continue
                end = close + len(m_raw.group(1)) + 2
                self._add_regular(regular_start, pos)
                self._blocks.append(
                    RawStringBlock(
                        content=text[pos:end],
                        start=self._line(pos),
                        end=self._line(end - 1),
                        delimiter=m_raw.group(1),
                    )
                )
                regular_start = pos = end
            else:  # delimited_string
                m_open = DELIMITED_OPEN_RE.match(text, pos)
                is_identifier = pos == 0 or not (text[pos - 1].isalnum() or text[pos - 1] == "_")
                close_end = _find_delimited_close(text, m_open.end()) if m_open is not None and is_identifier else None
                if close_end is None:
                    pos += len(token)
                    continue
                self._add_regular(regular_start, pos)
                self._blocks.append(
                    DelimitedStringBlock(
                        content=text[pos:close_end],
                        start=self._line(pos),
                        end=self._line(close_end - 1),
                        closer_indent=self._closer_indent(pos),
                    )
                )
                regular_start = pos = close_end
        self._add_regular(regular_start, len(text))
        self._mark_concatenated_raw_strings()

    def _closer_indent(self, pos: int) -> str:
        """Indentation clang-format gives the '})' of a delimited_string starting at ``pos``, once rewritten.

        It's the indentation of the line, unless the block is in an initializer list opened earlier on that line (eg
        ``{delimited_string({``): then '})' is aligned with ``delimited_string``.
        """
        line_start = self.content.rfind("\n", 0, pos) + 1
        prefix = self.content[line_start:pos]
        if "{" in prefix:
            return " " * len(prefix)
        return prefix[: len(prefix) - len(prefix.lstrip())]

    def _line(self, pos: int) -> int:
        """0-based line number of character ``pos``."""
        return self.content.count("\n", 0, pos)

    def _add_regular(self, start: int, end: int) -> None:
        if end > start:
            self._blocks.append(
                RegularCodeBlock(content=self.content[start:end], start=self._line(start), end=self._line(end - 1))
            )

    def _mark_concatenated_raw_strings(self) -> None:
        """Mark raw strings separated only by whitespace or comments: they are pieces of the same C++ string."""
        for i, block in enumerate(self._blocks):
            if not isinstance(block, RawStringBlock):
                continue
            between = self._blocks[i + 1] if i + 1 < len(self._blocks) else None
            following = self._blocks[i + 2] if i + 2 < len(self._blocks) else None
            if (
                isinstance(between, RegularCodeBlock)
                and isinstance(following, RawStringBlock)
                and not _strip_cpp_comments(between.content).strip()
            ):
                block.concatenated = following.concatenated = True

    def __repr__(self) -> str:
        return f"UnitTestFile with {len(self._blocks)} blocks:\n" + "\n".join(f"  {b!r}" for b in self._blocks)

# C++ unit test reformatter

Reformats the IDF snippets embedded in EnergyPlus C++ unit tests (`*.unit.cc`).

```
energyplus-toolkit format unit-test --idd Energy+.idd Foo.unit.cc [tst/EnergyPlus/unit ...] [--check | --diff | -o out.cc]
```

Everything is in `unit_test_file.py`.

## 1. Split the file into blocks

`UnitTestFile` cuts the file into consecutive blocks. Joining them back gives the original file, character for character.

It scans the file like a C++ compiler would: comments and string literals are skipped, so a `delimited_string({` in a `// comment` is not a block. A `delimited_string` block ends at the `})` matching its `({` (whatever follows, `);`, `));` or `, true));`, is regular code). A raw string ends at the first `)IDF"`.

| Block                  | What                                    | Is IDF if…                                      |
|------------------------|-----------------------------------------|-------------------------------------------------|
| `RegularCodeBlock`     | Any other C++ code                      | never                                           |
| `DelimitedStringBlock` | `delimited_string({ "...", "..." });`   | a string looks like an object type (`Zone,`)    |
| `RawStringBlock`       | `R"IDF( ... )IDF"`                      | the delimiter is `IDF`                          |

Only IDF blocks are reformatted. Everything else is left untouched.

## 2. Reformat each IDF block

1. Extract the IDF text (`idf_content`): the content of the quoted strings, or of the raw string. Like in C++, a string with no `,` after it is joined with the next one (that's how clang-format splits a long string).
2. Reformat it with `IdfFile`.
3. Write it back:
   - `delimited_string`: `delimited_string({` and `})` on their own lines, one `"...",` per line, a real blank line between objects. Thanks to the trailing comma on every line, clang-format keeps one string per line. Blocks written differently (first string on the `delimited_string({` line, `{` on the next line, last string on the `})` line) are rewritten that way, with the indentation clang-format would use.
   - `R"IDF(`: flush left, with a blank line after `R"IDF(` and before `)IDF"`.

## 3. Keep C++ comments (`delimited_string` only)

`//` comments sit between the strings, so they are not IDF. They are taken out before reformatting and put back after.

The problem: reformatting changes the lines (blank lines collapse, `Zone,Z1;` becomes two lines), so a comment can't be put back by line number. Instead, it is put back next to the same **IDF value**, identified by its position: *object N, field M*.

**While parsing** (`_parse_idf_content`): each comment is removed and stored as a `CppComment` with the *input* line it was on. Nothing else.

**While reformatting** (`_reformat`):

1. List every value in the **input** lines, with its position and line, by counting `,` (next field) and `;` (next object).
2. Turn each comment's input line into a value:
   - own line → the next value
   - inline (`"...", // ...`) → the value ending on that line
3. Reformat the IDF, then list every value in the **output** lines the same way.
4. Look up the comment's value in the output, and insert the comment before that line (or at its end, if inline).

```
input                       comment → value               output
"Zone,Z1,",                                               "Zone,",
// Before field 2           → object 0, field 2           "  Z1,     !- Name",
"  90;", // Inline          → object 0, field 2           // Before field 2
                                                          "  90.0;   !- Direction of Relative North {deg}", // Inline
```

Values are matched by position, never by text, so identical lines (eg two `"  90.1;",`) are not a problem.

Notes:

- A comment followed by blank lines moves down, right above the next value.
- A long inline comment wrapped by clang-format (next line `//`, aligned under it) is one comment: its continuation stays with it.
- `R"IDF(` blocks can't contain C++ comments: there, `//` is part of the string, which EnergyPlus would reject.

## 4. Don't undo clang-format

clang-format aligns trailing `//` comments, wraps long ones, and splits long strings in adjacent literals. The block is kept as is when the output only differs by that (compared token by token, `_cpp_tokens`), otherwise a pre-commit hook running this then clang-format would never be satisfied.

## When a block is left unchanged

If a block can't be reformatted safely, it is kept as is and a warning is logged. This happens when:

- the IDF can't be parsed, or an object type isn't in the IDD (`IdfFile` would drop it)
- a line has text that isn't part of a field, ie after its last `,` / `;` (`IdfFile` would drop it). Eg a value whose `,` is on the next line
- a line in a `delimited_string` isn't a string, a `//` comment, or blank (eg `std::format(...)`, `"..." + var + "..."`)
- `R"IDF(` / `)IDF"` aren't on their own lines
- a raw string is split in several pieces (`)IDF"` followed by `R"IDF(`, to avoid MSVC error C2026)
- the IDF contains `"` or `\` (would need C++ escaping)
- a comment's value can't be found after reformatting

## Tests

`tests/cpp/test_unit_test_file.py`. The main one reformats `tests/resources/cpp/Example.unit.cc` and compares it with `Example.unit.expected.cc`.

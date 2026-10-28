# C++ unit test reformatter

Reformats the IDF snippets embedded in EnergyPlus C++ unit tests (`*.unit.cc`).

```
python -m energyplus_parser.cli reformat_unit_test Foo.unit.cc --idd Energy+.idd [-o out.cc | -o -] [--overwrite]
```

Everything is in `unit_test_file.py`.

## 1. Split the file into blocks

`UnitTestFile` cuts the file into consecutive blocks. Joining them back gives the original file, character for character.

| Block                  | What                                    | Is IDF if…                                      |
|------------------------|-----------------------------------------|-------------------------------------------------|
| `RegularCodeBlock`     | Any other C++ code                      | never                                           |
| `DelimitedStringBlock` | `delimited_string({ "...", "..." });`   | a string looks like an object type (`Zone,`)    |
| `RawStringBlock`       | `R"IDF( ... )IDF"`                      | the delimiter is `IDF`                          |

Only IDF blocks are reformatted. Everything else is left untouched.

## 2. Reformat each IDF block

1. Extract the IDF text (`idf_content`): the content of the quoted strings, or of the raw string.
2. Reformat it with `IdfFile`.
3. Write it back:
   - `delimited_string`: one `"...",` per line, a real blank line between objects.
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
- `R"IDF(` blocks can't contain C++ comments: there, `//` is part of the string, which EnergyPlus would reject.

## When a block is left unchanged

Nothing is ever lost: if a block can't be reformatted safely, it is kept as is and a warning is logged. This happens when:

- an object type isn't in the IDD (`IdfFile` would drop it)
- a line in a `delimited_string` isn't a string, a `//` comment, or blank
- `delimited_string({` / `});` or `R"IDF(` / `)IDF"` aren't on their own lines
- the IDF contains `"` or `\` (would need C++ escaping)
- a comment's value can't be found after reformatting

## Tests

`tests/cpp/test_unit_test_file.py`. The main one reformats `tests/resources/cpp/Example.unit.cc` and compares it with `Example.unit.expected.cc`.

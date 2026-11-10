# energyplus-toolkit

[![pypi](https://img.shields.io/pypi/v/energyplus-toolkit.svg)](https://pypi.org/project/energyplus-toolkit/)
[![python](https://img.shields.io/pypi/pyversions/energyplus-toolkit.svg)](https://pypi.org/project/energyplus-toolkit/)
[![Build Status](https://github.com/jmarrec/energyplus-toolkit/actions/workflows/dev.yml/badge.svg)](https://github.com/jmarrec/energyplus-toolkit/actions/workflows/dev.yml)

Tools for [EnergyPlus](https://energyplus.net) input files:

- parse IDD and IDF files, link each IDF object and field to its IDD definition, and write them back faithfully;
- reformat IDF and IDD files, and the IDF embedded in EnergyPlus C++ unit tests, from the command line or as
  pre-commit hooks.

- GitHub: <https://github.com/jmarrec/energyplus-toolkit>
- PyPI: <https://pypi.org/project/energyplus-toolkit/>

## Installation

```bash
pip install energyplus-toolkit
```

Requires Python 3.11+.

For development:

```bash
pip install -e ".[dev,test]"  # With the dev tools (pre-commit, black, isort, flake8, mypy) and the tests (pytest)
pre-commit install
```

## Command line

```shell
# Reformat in place, like black: files and/or folders (searched recursively), in parallel
energyplus-toolkit format idf --idd Energy+.idd testfiles/
energyplus-toolkit format idd Energy+.idd
energyplus-toolkit format unit-test --idd Energy+.idd tst/EnergyPlus/unit

# Only look: list the files that would change (exit 1 if any), or print a diff
energyplus-toolkit format idf --idd Energy+.idd --check testfiles/
energyplus-toolkit format idf --idd Energy+.idd --diff testfiles/1ZoneUncontrolled.idf
```

All the options are listed in [Options](#options).

Exit codes: 0 when done, 1 if `--check` found files to reformat, 123 on error.

Content is never lost: a file or block that can't be reformatted safely (unknown object, text outside a field, IMF or
parametric file, C++ code building the IDF...) is left unchanged, with a warning.

## Linting IDD files

```shell
energyplus-toolkit lint idd Energy+.idd
energyplus-toolkit lint idd --fail-on warning --output-format json idd/
```

Reports what parses but looks wrong, without changing the file: field ids that aren't consecutive, malformed extensible
groups, a `\type` that doesn't match the field id, `\units` and `\ip-units` that don't match the units table of the
header (errors), a `\required-field` with a `\default` (warning), and an `\ip-units` that is already the default (info).

Exit codes: 0 if nothing reached `--fail-on` (`error` by default), 1 otherwise.

Info messages are counted in the summary but only printed with `--verbose` (or `--fail-on info`).

The text output is colored on a terminal and in GitHub Actions; `NO_COLOR` turns colors off, `FORCE_COLOR` forces them
on.

## Options

| Option | Commands | `pyproject.toml` key | Default | What it does |
|---|---|---|---|---|
| `--idd PATH` | `format idf`, `format unit-test` | `idd` | required | The IDD to read the IDF with. |
| `--check` | `format` | | | Don't write: list the files that would change, exit 1 if any. |
| `--diff` | `format` | | | Don't write: print a unified diff of the changes. |
| `-o PATH`, `--output PATH` | `format` | | | Write to this file instead of in place (`-` for stdout). Only with a single input file. |
| `--exclude REGEX` | all | `exclude` | | Skip the files found in folders whose path matches. Files given explicitly are always processed. |
| `-j N`, `--workers N` | `format` | `workers` | number of CPUs | Number of parallel processes. |
| `-q`, `--quiet` | `format` | `quiet` | `false` | Only print errors and the summary. |
| `--leading N` | `format idf`, `format unit-test` | `leading` | `0` | Spaces before each object type line. |
| `--keep-integer-reals` | `format idf`, `format unit-test` | `keep-integer-reals` | `false` | Keep a number written as an integer as is in a real field (`8`, not `8.0`). Always the case for Number of Vertices. |
| `--tag-column N` | `format idd` | `tag-column` | `7` | Column where the `\` of field and tag lines starts (`\field`, `\note`...). At least 6. |
| `--fail-on LEVEL` | `lint idd` | `fail-on` | `error` | Exit 1 if a message is at least this severe: `info`, `warning` or `error`. |
| `--output-format FORMAT` | `lint idd` | `output-format` | `text` | `text`, `json` (one object per message, with the keys of EnergyPlus' `scripts/dev/base_hook.py`) or `gha` (GitHub Actions annotations). |
| `-v`, `--verbose` | `lint idd` | `verbose` | `false` | Also print the info messages, which are only counted otherwise. |
| `--config PATH` | all | | closest `pyproject.toml` | Read the defaults from the `[tool.energyplus-toolkit]` table of this file. |

`format` is `format idf`, `format idd` and `format unit-test`.

The IDF field indent (2) and the column of its `!-` comments (27) are only settable from Python, with `FormatOptions`.

## Configuration

The options' defaults can go in the `[tool.energyplus-toolkit]` table of a `pyproject.toml`, like black's
`[tool.black]`. Its keys are the long option names: each applies to the commands that have that option, and the command
line wins.

```toml
[tool.energyplus-toolkit]
idd = "idd/Energy+.idd.in"  # Relative to the pyproject.toml
fail-on = "warning"
```

It's read from the closest `pyproject.toml`, from the current folder up to the repository root, or from `--config PATH`.
An unknown key is an error. `--check`, `--diff` and `-o` aren't settings: they say what a single run does.

## pre-commit hooks

```yaml
- repo: https://github.com/jmarrec/energyplus-toolkit
  rev: v0.3.0
  hooks:
  - id: energyplus-format-idd
    args: [-q]
    # Example to limit to a specific file
    files: ^idd/Energy\+\.idd\.in$
  - id: energyplus-format-idf
    args: [--idd, idd/Energy+.idd.in, -q]
  - id: energyplus-format-unit-test
    args: [--idd, idd/Energy+.idd.in, -q]
  - id: energyplus-lint-idd
    files: ^idd/Energy\+\.idd\.in$
```

The IDF and unit test hooks need the IDD to use (`--idd`); the IDD hooks don't take it.
The lint hook fails on errors (`--fail-on` to change it), and doesn't change the file.
`files` is optional: it limits a hook to the paths matching this regex, here the one IDD to format.

**Note:** For unit tests, put the hook before clang-format: reformatting then clang-format is stable.

## Library

The IDD gives each IDF object and field its definition: type, units, default, choices, extensible groups...

```python
from pathlib import Path

from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.idf.idf_file import IdfFile
from energyplus_toolkit.input.idf.idf_object import IdfObject

idd = IddFile.load(Path("Energy+.idd"))

# A whole IDF file: each object is linked to its IDD object
idf = IdfFile.load(Path("in.idf"), idd_file=idd)  # or IdfFile.loads(text, idd)
for zone in idf.get_objects_by_type("Zone"):
    print(zone.name, zone.getDouble(1), zone.getDouble(1, return_default=True))  # "Z2 None 0.0" if left blank
idf.save("out.idf", overwrite=True)  # or str(idf)

# A single object, from its text and its IDD object
zone = IdfObject.load(idd_object=idd.getObject("Zone"), text="Zone,Z3,90;")
zone.setDouble(1, 45.0)
print(zone)
# Zone,
#   Z3,                      !- Name
#   45.0;                    !- Direction of Relative North {deg}
idf.add_object(obj=zone)

# Or built from scratch, with extensible groups
branch = IdfObject(idd_object=idd.getObject("Branch"))
branch.setString(0, "Supply Branch")
branch.push_extensible_group(["Pump:VariableSpeed", "Pump", "Pump-Inlet", "Pump-Outlet"])

idf.remove_object(zone)
idf.add_objects(objs=[zone, branch])
assert idf.objects[-2:] == [zone, branch]

# The IDD side
field = idd.getObject("Zone").fields[1]
print(field.name, field.properties.type, field.properties.units, field.properties.stringDefault)
# Direction of Relative North real deg 0
```

Values are validated against the IDD when set: types, choices (the casing is normalized), bounds.
The IDF is written with its comments (`!- Field Name {units}`) and the layout the IDD asks for (`\format`: vertices, compact schedules...).

## Layout

- `energyplus_toolkit/input`: the EnergyPlus input data model (IDD and IDF objects, fields, their types), read from and
  written to files. It doesn't depend on the tools, so it can become its own package.
- `energyplus_toolkit/format`: the formatter (parallel runner, C++ unit tests: see `format/cpp/README.md`).
- `energyplus_toolkit/cli.py`: the `energyplus-toolkit` command.

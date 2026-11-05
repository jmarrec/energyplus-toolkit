# energyplus-toolkit

[![pypi](https://img.shields.io/pypi/v/energyplus-toolkit.svg)](https://pypi.org/project/energyplus-toolkit/)
[![python](https://img.shields.io/pypi/pyversions/energyplus-toolkit.svg)](https://pypi.org/project/energyplus-toolkit/)
[![Build Status](https://github.com/jmarrec/energyplus-toolkit/actions/workflows/dev.yml/badge.svg)](https://github.com/jmarrec/energyplus-toolkit/actions/workflows/dev.yml)

Tools for [EnergyPlus](https://energyplus.net) input files:

- parse IDD and IDF files, link each IDF object and field to its IDD definition, and write them back faithfully;
- reformat IDF and IDD files, and the IDF embedded in EnergyPlus C++ unit tests, from the command line or as
  pre-commit hooks.

* GitHub: <https://github.com/jmarrec/energyplus-toolkit>
* PyPI: <https://pypi.org/project/energyplus-toolkit/>

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

Options (see `--help`): `--exclude REGEX`, `-j N` workers, `-q` quiet, `-o OUTPUT` (single file, `-` for stdout),
and for IDF / unit tests `--leading N` (spaces before object names) and `--keep-integer-reals` (keep `8` instead of
writing `8.0` in a real field).

Exit codes: 0 when done, 1 if `--check` found files to reformat, 123 on error.

Content is never lost: a file or block that can't be reformatted safely (unknown object, text outside a field, IMF or
parametric file, C++ code building the IDF...) is left unchanged, with a warning.

## pre-commit hooks

```yaml
- repo: https://github.com/jmarrec/energyplus-toolkit
  rev: v0.1.1
  hooks:
  - id: energyplus-format-idd
    args: [--idd, idd/Energy+.idd.in]
  - id: energyplus-format-idf
    args: [--idd, idd/Energy+.idd.in, -q]
  - id: energyplus-format-unit-test
    args: [--idd, idd/Energy+.idd.in, -q]
```

Each hook needs the IDD to use (`--idd`). For unit tests, put the hook before clang-format: reformatting then
clang-format is stable.

## Library

The IDD gives each IDF object and field its definition: type, units, default, choices, extensible groups...

```python
from pathlib import Path

from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.idf.idf_file import IdfFile
from energyplus_toolkit.input.idf.idf_object import IdfObject

idd = IddFile.load(Path("Energy+.idd"))

# A whole IDF file: each object is linked to its IDD object
idf = IdfFile.load("in.idf", idd)  # or IdfFile.loads(text, idd)
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

# Or built from scratch, with extensible groups
branch = IdfObject(idd_object=idd.getObject("Branch"))
branch.setString(0, "Supply Branch")
branch.push_extensible_group(["Pump:VariableSpeed", "Pump", "Pump-Inlet", "Pump-Outlet"])

# The IDD side
field = idd.getObject("Zone").fields[1]
print(field.name, field.properties.type, field.properties.units, field.properties.stringDefault)
# Direction of Relative North real deg 0
```

Values are validated against the IDD when set (types, choices, bounds), and the IDF is written with its comments
(`!- Field Name {units}`) and the layout the IDD asks for (`\format`: vertices, compact schedules...).

## Layout

- `energyplus_toolkit/input`: the EnergyPlus input data model (IDD and IDF objects, fields, their types), read from and
  written to files. It doesn't depend on the tools, so it can become its own package.
- `energyplus_toolkit/format`: the formatter (parallel runner, C++ unit tests: see `format/cpp/README.md`).
- `energyplus_toolkit/cli.py`: the `energyplus-toolkit` command.

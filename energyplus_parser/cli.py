"""Command-line interface for the EnergyPlus IDF/IDD parser."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from energyplus_parser.cpp.unit_test_file import UnitTestFile
from energyplus_parser.idd.idd_file import IddFile
from energyplus_parser.idf import idf_constants
from energyplus_parser.idf.idf_file import IdfFile

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _resolve_output(input_path: Path, output_path: Path | None, overwrite: bool, suffix: str) -> Path | None:
    """Return the resolved output Path, or None when writing to stdout."""
    if output_path is not None and str(output_path) == "-":
        return None  # stdout
    if output_path is None:
        return input_path if overwrite else input_path.with_name(input_path.stem + suffix)
    return output_path


def _write_output(text: str, output_path: Path | None, overwrite: bool) -> None:
    if output_path is None:
        sys.stdout.write(text)
    else:
        if output_path.exists() and not overwrite:
            print(f"Error: {output_path} already exists. Use --overwrite to allow.", file=sys.stderr)
            sys.exit(1)
        output_path.write_text(text, encoding="utf-8")
        print(f"Written to: {output_path}")


# ---------------------------------------------------------------------------
# reformat_idf subcommand
# ---------------------------------------------------------------------------


def _add_reformat_idf(subparsers) -> None:
    p = subparsers.add_parser(
        "reformat_idf",
        help="Parse and re-serialise an EnergyPlus IDF file.",
        description="Parse an IDF file using the given IDD and write the reformatted result.",
    )
    p.add_argument("idf_path", type=Path, help="Path to the input IDF file.")
    p.add_argument(
        "--idd",
        dest="idd_path",
        type=Path,
        required=True,
        metavar="IDD_PATH",
        help="Path to the EnergyPlus IDD file.",
    )
    p.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=Path,
        default=None,
        metavar="OUTPUT_PATH",
        help=(
            "Path to write the serialised IDF. "
            "Defaults to <idf_path>.out.idf when not specified. "
            "Pass '-' to write to stdout."
        ),
    )
    p.add_argument(
        "--leading",
        dest="idf_leading",
        type=int,
        default=None,
        metavar="N",
        help=(
            f"Leading spaces before each object-type name line "
            f"(IDF_LEADING constant, default: {idf_constants.IDF_LEADING})."
        ),
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    p.set_defaults(func=_cmd_reformat_idf)


def _cmd_reformat_idf(args, parser) -> None:
    idf_path: Path = args.idf_path
    idd_path: Path = args.idd_path

    if not idf_path.exists():
        parser.error(f"IDF file not found: {idf_path}")
    if not idd_path.exists():
        parser.error(f"IDD file not found: {idd_path}")

    if args.idf_leading is not None:
        if args.idf_leading < 0:
            parser.error("--leading must be a non-negative integer.")
        idf_constants.IDF_LEADING = args.idf_leading

    idd = IddFile.load(idd_path)
    idf = IdfFile.load(idf_path, idd)

    output_path = _resolve_output(idf_path, args.output_path, args.overwrite, ".out.idf")
    _write_output(str(idf), output_path, args.overwrite)


# ---------------------------------------------------------------------------
# reformat_idd subcommand
# ---------------------------------------------------------------------------


def _add_reformat_idd(subparsers) -> None:
    p = subparsers.add_parser(
        "reformat_idd",
        help="Parse and re-serialise an EnergyPlus IDD file.",
        description="Parse an IDD file and write the reformatted result.",
    )
    p.add_argument("idd_path", type=Path, help="Path to the input IDD file.")
    p.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=Path,
        default=None,
        metavar="OUTPUT_PATH",
        help=(
            "Path to write the serialised IDD. "
            "Defaults to <idd_path>.out.idd when not specified. "
            "Pass '-' to write to stdout."
        ),
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    p.set_defaults(func=_cmd_reformat_idd)


def _cmd_reformat_idd(args, parser) -> None:
    idd_path: Path = args.idd_path

    if not idd_path.exists():
        parser.error(f"IDD file not found: {idd_path}")

    idd = IddFile.load(idd_path)

    output_path = _resolve_output(idd_path, args.output_path, args.overwrite, ".out.idd")
    _write_output(str(idd), output_path, args.overwrite)


# ---------------------------------------------------------------------------
# reformat_unit_test subcommand
# ---------------------------------------------------------------------------


def _add_reformat_unit_test(subparsers) -> None:
    p = subparsers.add_parser(
        "reformat_unit_test",
        help="Reformat IDF content embedded in a C++ EnergyPlus unit test file.",
        description=(
            "Parse and reformat IDF blocks inside delimited_string({...}) and "
            "R\"IDF(...)IDF\" blocks in a C++ unit test file."
        ),
    )
    p.add_argument("cc_path", type=Path, help="Path to the input .unit.cc file.")
    p.add_argument(
        "--idd",
        dest="idd_path",
        type=Path,
        required=True,
        metavar="IDD_PATH",
        help="Path to the EnergyPlus IDD file.",
    )
    p.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=Path,
        default=None,
        metavar="OUTPUT_PATH",
        help=(
            "Path to write the reformatted file. "
            "Defaults to <cc_path>.out.cc when not specified. "
            "Pass '-' to write to stdout."
        ),
    )
    p.add_argument(
        "--leading",
        dest="idf_leading",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Leading spaces before each object-type name line "
            f"(IDF_LEADING constant, defaults to {idf_constants.IDF_LEADING})."
        ),
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    p.set_defaults(func=_cmd_reformat_unit_test)


def _cmd_reformat_unit_test(args, parser) -> None:
    cc_path: Path = args.cc_path
    idd_path: Path = args.idd_path

    if not cc_path.exists():
        parser.error(f"C++ file not found: {cc_path}")
    if not idd_path.exists():
        parser.error(f"IDD file not found: {idd_path}")

    if args.idf_leading is not None:
        if args.idf_leading < 0:
            parser.error("--leading must be a non-negative integer.")
        idf_constants.IDF_LEADING = args.idf_leading

    idd = IddFile.load(idd_path)

    unit_test_file = UnitTestFile.from_path(cc_path)

    output_path = _resolve_output(cc_path, args.output_path, args.overwrite, ".out.cc")
    _write_output(unit_test_file.reformat(idd), output_path, args.overwrite)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="energyplus-parser",
        description="Parse and re-serialise EnergyPlus IDF/IDD files.",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True
    _add_reformat_idf(subparsers)
    _add_reformat_idd(subparsers)
    _add_reformat_unit_test(subparsers)
    return parser


def main(args_: list[str] | None = None) -> None:
    parser = get_parser()
    args = parser.parse_args(args_)
    args.func(args, parser)


if __name__ == "__main__":  # pragma: no cover
    main()

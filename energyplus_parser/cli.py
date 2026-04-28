"""Command-line interface for the EnergyPlus IDF parser."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from energyplus_parser.idd.idd_file import IddFile
from energyplus_parser.idf import idf_constants
from energyplus_parser.idf.idf_file import IdfFile


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="energyplus-parser",
        description="Parse and re-serialise an EnergyPlus IDF file.",
    )
    parser.add_argument(
        "idf_path",
        type=Path,
        help="Path to the input IDF file.",
    )
    parser.add_argument(
        "--idd",
        dest="idd_path",
        type=Path,
        required=True,
        metavar="IDD_PATH",
        help="Path to the EnergyPlus IDD file.",
    )
    parser.add_argument(
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
    parser.add_argument(
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
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    return parser


def main(args_: list[str] | None = None) -> None:
    parser = get_parser()
    args = parser.parse_args(args_)

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

    output_path: Path | None = args.output_path
    to_stdout = output_path is not None and str(output_path) == "-"

    if to_stdout:
        sys.stdout.write(str(idf))
    else:
        if output_path is None:
            output_path = idf_path.with_suffix("").with_name(idf_path.stem + ".out.idf")
        idf.save(output_path, overwrite=args.overwrite)
        print(f"Written to: {output_path}")


if __name__ == "__main__":  # pragma: no cover
    main()

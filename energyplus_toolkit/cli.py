"""Command-line interface: energyplus-toolkit COMMAND ...

energyplus-toolkit format idf|idd|unit-test PATH...: works like black, give it files and/or folders, they are
reformatted in place, in parallel. Use --check or --diff to only see what would change.

energyplus-toolkit lint idd PATH...: report what is wrong in IDD files, without changing them.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from energyplus_toolkit.format import runner
from energyplus_toolkit.format.runner import Job, Kind, Mode
from energyplus_toolkit.input.idf import idf_constants
from energyplus_toolkit.input.log_message import LogLevel
from energyplus_toolkit.lint import idd as lint_idd

DESCRIPTIONS = {
    Kind.IDF: "Reformat EnergyPlus IDF files.",
    Kind.IDD: "Reformat EnergyPlus IDD files.",
    Kind.UNIT_TEST: (
        'Reformat the IDF embedded in EnergyPlus C++ unit tests, in delimited_string({...}) and R"IDF(...)IDF" blocks.'
    ),
}


def _add_format_subcommand(subparsers, name: str, kind: Kind) -> None:
    p = subparsers.add_parser(name, help=DESCRIPTIONS[kind], description=DESCRIPTIONS[kind])
    patterns = ", ".join(f"*{s}" for s in kind.suffixes)
    p.add_argument(
        "paths",
        type=Path,
        nargs="+",
        metavar="PATH",
        help=f"Files or folders. Folders are searched recursively for {patterns}.",
    )
    if kind.needs_idd:
        p.add_argument(
            "--idd", dest="idd_path", type=Path, required=True, metavar="IDD_PATH", help="Path to the IDD file."
        )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--check", action="store_true", help="Don't write: list the files that would change, exit 1 if any."
    )
    mode.add_argument("--diff", action="store_true", help="Don't write: print a unified diff of the changes.")
    mode.add_argument(
        "-o",
        "--output",
        dest="output_path",
        type=Path,
        metavar="OUTPUT_PATH",
        help="Write to this file instead of in place ('-' for stdout). Only with a single input file.",
    )
    p.add_argument(
        "--exclude",
        type=re.compile,
        metavar="REGEX",
        help="Skip files found in folders whose path matches this regex. Files given explicitly are always processed.",
    )
    p.add_argument(
        "-j",
        "--workers",
        type=int,
        default=None,
        metavar="N",
        help="Number of parallel processes (default: number of CPUs).",
    )
    p.add_argument("-q", "--quiet", action="store_true", help="Only print errors and the summary.")
    if kind is not Kind.IDD:
        p.add_argument(
            "--leading",
            dest="idf_leading",
            type=int,
            default=None,
            metavar="N",
            help=f"Leading spaces before each object-type line (default: {idf_constants.IDF_LEADING}).",
        )
        p.add_argument(
            "--keep-integer-reals",
            action="store_true",
            help='Keep a number written as an integer as is in a real field ("8" instead of "8.0").',
        )
    p.set_defaults(kind=kind)


def _add_lint_idd_subcommand(subparsers) -> None:
    description = "Report problems in EnergyPlus IDD files, which aren't changed."
    p = subparsers.add_parser("idd", help=description, description=description)
    patterns = ", ".join(f"*{s}" for s in Kind.IDD.suffixes)
    p.add_argument(
        "paths",
        type=Path,
        nargs="+",
        metavar="PATH",
        help=f"Files or folders. Folders are searched recursively for {patterns}.",
    )
    p.add_argument(
        "--exclude",
        type=re.compile,
        metavar="REGEX",
        help="Skip files found in folders whose path matches this regex. Files given explicitly are always processed.",
    )
    p.add_argument(
        "--fail-on",
        type=str.upper,
        choices=[level.name for level in LogLevel],
        default=LogLevel.ERROR.name,
        help="Exit 1 if a message is at least this severe (default: error).",
    )
    p.add_argument(
        "--output-format",
        type=lint_idd.OutputFormat,
        default=lint_idd.OutputFormat.TEXT,
        metavar="{text,json,gha}",
        help=(
            "text, one JSON object per message with the keys of EnergyPlus' base_hook.py, or gha: GitHub Actions "
            "annotations (default: text)."
        ),
    )
    p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Also print the info messages, which are only counted otherwise (always printed with --fail-on info).",
    )


def _lint(args) -> int:
    files = runner.collect_files(args.paths, Kind.IDD, args.exclude)
    if not files:
        print("No files to lint.", file=sys.stderr)
        return 0
    messages = [msg for path in files for msg in lint_idd.lint_file(path)]
    return lint_idd.report(
        messages, fail_on=LogLevel[args.fail_on], output_format=args.output_format, verbose=args.verbose
    )


def get_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="energyplus-toolkit", description="Tools for EnergyPlus input files.")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.required = True

    format_parser = commands.add_parser(
        "format", help="Reformat EnergyPlus files.", description="Reformat EnergyPlus files."
    )
    kinds = format_parser.add_subparsers(dest="kind_name", metavar="KIND")
    kinds.required = True
    _add_format_subcommand(kinds, "idf", Kind.IDF)
    _add_format_subcommand(kinds, "idd", Kind.IDD)
    _add_format_subcommand(kinds, "unit-test", Kind.UNIT_TEST)

    lint_parser = commands.add_parser("lint", help="Report problems in EnergyPlus files.")
    lint_kinds = lint_parser.add_subparsers(dest="kind_name", metavar="KIND")
    lint_kinds.required = True
    _add_lint_idd_subcommand(lint_kinds)
    return parser


def _make_job(args, parser: argparse.ArgumentParser) -> Job:
    kind: Kind = args.kind
    idd_path = getattr(args, "idd_path", None)
    if idd_path is not None and not idd_path.is_file():
        parser.error(f"IDD file not found: {idd_path}")
    constants: list[tuple[str, object]] = []
    if getattr(args, "idf_leading", None) is not None:
        if args.idf_leading < 0:
            parser.error("--leading must be a non-negative integer.")
        constants.append(("IDF_LEADING", args.idf_leading))
    if getattr(args, "keep_integer_reals", False):
        constants.append(("IDF_KEEP_INTEGER_REALS", True))
    mode = Mode.CHECK if args.check else Mode.DIFF if args.diff else Mode.WRITE
    return Job(kind=kind, mode=mode, idd_path=idd_path, constants=tuple(constants))


def main(args_: list[str] | None = None) -> int:
    parser = get_parser()
    args = parser.parse_args(args_)

    for path in args.paths:
        if not path.exists():
            parser.error(f"path not found: {path}")
    if args.command == "lint":
        return _lint(args)
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be at least 1.")
    job = _make_job(args, parser)

    if args.output_path is not None:
        # Single file, written elsewhere
        if len(args.paths) != 1 or args.paths[0].is_dir():
            parser.error("-o/--output needs exactly one input file.")
        runner.init_worker(job)
        text = runner.reformat_text(job.kind, args.paths[0].read_text(encoding="utf-8"))
        if str(args.output_path) == "-":
            sys.stdout.write(text)
        else:
            args.output_path.write_text(text, encoding="utf-8")
        return 0

    files = runner.collect_files(args.paths, job.kind, args.exclude)
    if not files:
        print("No files to reformat.", file=sys.stderr)
        return 0
    results = runner.run(files, job, workers=args.workers)
    return runner.report(results, job, quiet=args.quiet)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

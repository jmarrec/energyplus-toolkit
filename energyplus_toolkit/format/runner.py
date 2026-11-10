"""Reformat many files in place, in parallel, black-style.

The reformatters (IDF, IDD, C++ unit tests) only differ by how a file's text is turned into its reformatted text.
Everything else is shared: finding files in folders, the write / check / diff modes, the process pool, collecting the
warnings of each file, and the summary.

The IDD is loaded once: in the main process before the pool starts, so that forked workers inherit it. Where fork isn't
available, each worker loads it in its initializer.
"""

from __future__ import annotations

import difflib
import logging
import multiprocessing
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from energyplus_toolkit.format.cpp.unit_test_file import UnitTestFile
from energyplus_toolkit.input.format_options import DEFAULT_FORMAT_OPTIONS, FormatOptions
from energyplus_toolkit.input.idd.idd_file import IddFile
from energyplus_toolkit.input.idf.idf_file import IdfFile, find_lost_objects, find_text_outside_fields

LOG = logging.getLogger("Runner")

# Parametric objects mean the IDF is input for EnergyPlus' parametric preprocessor, with expressions like "=$height" in
# its fields: it isn't a valid IDF until it's been preprocessed
_PARAMETRIC_RE = re.compile(r"^\s*Parametric:", re.MULTILINE | re.IGNORECASE)


class Kind(Enum):
    IDF = "idf"
    IDD = "idd"
    UNIT_TEST = "unit_test"

    @property
    def suffixes(self) -> tuple[str, ...]:
        """File name endings searched for in folders."""
        return {Kind.IDF: (".idf",), Kind.IDD: (".idd", ".idd.in"), Kind.UNIT_TEST: (".unit.cc",)}[self]

    @property
    def ignored_suffixes(self) -> tuple[str, ...]:
        """File name endings skipped, even when given explicitly (eg by pre-commit)."""
        return {Kind.IDF: (".imf",)}.get(self, ())

    @property
    def needs_idd(self) -> bool:
        return self is not Kind.IDD


class Mode(Enum):
    WRITE = "write"  # reformat in place
    CHECK = "check"  # don't write, report files that would change
    DIFF = "diff"  # don't write, print a unified diff


@dataclass(frozen=True)
class Job:
    """What to do with each file. Picklable, so it can be sent to spawned workers."""

    kind: Kind
    mode: Mode
    idd_path: Path | None = None
    format_options: FormatOptions = DEFAULT_FORMAT_OPTIONS  # How the IDF, IDD and unit test IDF are laid out


@dataclass
class Result:
    path: Path
    changed: bool = False
    error: str | None = None
    warnings: list[str] = field(default_factory=list)
    diff: str = ""


# ---------------------------------------------------------------------------
# Finding files
# ---------------------------------------------------------------------------


def collect_files(paths: list[Path], kind: Kind, exclude: re.Pattern[str] | None = None) -> list[Path]:
    """Expand folders (recursively) into the files of this kind, skipping those matching ``exclude``.

    Files given explicitly are always kept, like black does.
    """
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            for f in sorted(path.rglob("*")):
                if not f.is_file() or not f.name.endswith(kind.suffixes):
                    continue
                if exclude is not None and exclude.search(f.as_posix()):
                    continue
                files.append(f)
        elif not path.name.endswith(kind.ignored_suffixes):
            files.append(path)
    return list(dict.fromkeys(files))  # dedupe, keeping order


# ---------------------------------------------------------------------------
# Worker side
# ---------------------------------------------------------------------------

_job: Job | None = None
_idd: IddFile | None = None


def init_worker(job: Job) -> None:
    """Load the IDD, unless already done (eg inherited through fork)."""
    global _job, _idd
    if _job == job:
        return
    if not job.kind.needs_idd or job.idd_path is None:
        _idd = None
    elif _idd is None or _job is None or _job.idd_path != job.idd_path:
        _idd = IddFile.load(job.idd_path)
    _job = job


def reformat_text(kind: Kind, text: str, format_options: FormatOptions = DEFAULT_FORMAT_OPTIONS) -> str:
    """``text`` reformatted, laid out according to ``format_options``."""
    if kind is Kind.IDD:
        return IddFile.fromString(text).to_string(format_options)
    assert _idd is not None, "init_worker must be called first"
    if kind is Kind.IDF:
        if _PARAMETRIC_RE.search(text):
            LOG.warning("Parametric objects (needs the parametric preprocessor) — leaving unchanged")
            return text
        # Never lose content: leave the file unchanged if IdfFile would drop some of it
        if (line := find_text_outside_fields(text)) is not None:
            LOG.warning(f"text outside of an IDF field would be lost ({line!r}) — leaving unchanged")
            return text
        idf = IdfFile.loads(text, _idd)
        if (reason := find_lost_objects(text, idf)) is not None:
            LOG.warning(f"{reason} — leaving unchanged")
            return text
        return idf.to_string(format_options)
    return UnitTestFile(text).reformat(_idd, format_options)


class _Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def process_file(path: Path) -> Result:
    """Reformat one file according to the current job. Never raises: errors are reported in the Result."""
    assert _job is not None, "init_worker must be called first"
    result = Result(path=path)
    collect = _Collect()
    root = logging.getLogger()
    root.addHandler(collect)
    try:
        with open(path, encoding="utf-8", newline="") as f:
            original = f.read()
        crlf = "\r\n" in original
        new = reformat_text(_job.kind, original.replace("\r\n", "\n"), _job.format_options)
        if not new.endswith("\n") and original.endswith(("\n", "\r\n")):
            new += "\n"
        if crlf:
            new = new.replace("\n", "\r\n")
        result.changed = new != original
        if result.changed:
            if _job.mode is Mode.WRITE:
                with open(path, "w", encoding="utf-8", newline="") as f:
                    f.write(new)
            elif _job.mode is Mode.DIFF:
                result.diff = "".join(
                    difflib.unified_diff(
                        original.splitlines(keepends=True),
                        new.splitlines(keepends=True),
                        fromfile=f"{path}\t(original)",
                        tofile=f"{path}\t(reformatted)",
                    )
                )
    except Exception as exc:  # noqa: BLE001 - one bad file must not stop the others
        result.error = f"{type(exc).__name__}: {exc}"
    finally:
        root.removeHandler(collect)
    result.warnings = collect.messages
    return result


# ---------------------------------------------------------------------------
# Main side
# ---------------------------------------------------------------------------


def run(files: list[Path], job: Job, workers: int | None = None) -> list[Result]:
    """Process the files, in a process pool if there are several files and workers."""
    workers = workers or os.cpu_count() or 1
    init_worker(job)  # in the main process: forked workers inherit the loaded IDD
    if workers == 1 or len(files) < 2:
        return [process_file(f) for f in files]

    # Largest files first, so the long ones don't end up running alone at the end
    order = sorted(files, key=lambda f: f.stat().st_size if f.exists() else 0, reverse=True)
    method = "fork" if "fork" in multiprocessing.get_all_start_methods() else None
    with ProcessPoolExecutor(
        max_workers=min(workers, len(files)),
        mp_context=multiprocessing.get_context(method),
        initializer=init_worker,
        initargs=(job,),
    ) as pool:
        by_path = dict(zip(order, pool.map(process_file, order)))
    return [by_path[f] for f in files]


def report(results: list[Result], job: Job, quiet: bool = False, out=None, err=None) -> int:
    """Print what happened and return the exit code: 123 on error, 1 if --check found files to reformat, else 0."""
    out = out or sys.stdout
    err = err or sys.stderr
    n_changed = n_errors = 0
    for r in results:
        if r.error is not None:
            n_errors += 1
            print(f"error: cannot reformat {r.path}: {r.error}", file=err)
            continue
        if not quiet:
            for w in r.warnings:
                print(f"{r.path}: warning: {w}", file=err)
        if r.changed:
            n_changed += 1
            if job.mode is Mode.DIFF:
                out.write(r.diff)
            if not quiet:
                verb = "reformatted" if job.mode is Mode.WRITE else "would reformat"
                print(f"{verb} {r.path}", file=err)

    n_unchanged = len(results) - n_changed - n_errors
    verb = "reformatted" if job.mode is Mode.WRITE else "would be reformatted"
    parts = []
    if n_changed or not (n_unchanged or n_errors):
        parts.append(f"{n_changed} file{'s' if n_changed != 1 else ''} {verb}")
    if n_unchanged:
        verb = "left unchanged" if job.mode is Mode.WRITE else "would be left unchanged"
        parts.append(f"{n_unchanged} file{'s' if n_unchanged != 1 else ''} {verb}")
    if n_errors:
        parts.append(f"{n_errors} file{'s' if n_errors != 1 else ''} failed to reformat")
    print(", ".join(parts) + ".", file=err)

    if n_errors:
        return 123
    if job.mode is Mode.CHECK and n_changed:
        return 1
    return 0

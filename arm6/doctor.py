"""Look at this machine and say what is actually here, so a report can be believed.

Two things this package needs are things it is not allowed to carry: the ARM60
datasheet, which is nobody's to redistribute, and the conformance corpus, which
belongs to its own project. Both are therefore absent on somebody's machine, and
the checks that need them skip. A skip and a pass print the same thing, which is
why this exists.

There is a third here that the other members do not have. The ARM60 datasheet
carries no text layer at all: asking `pdftotext` for its contents returns one
newline per page and nothing else. So checking a quote against it needs the page
rendered and recognised, and a machine without a recogniser cannot check a single
quotation no matter how many documents it holds. That is reported as its own
finding rather than folded into the documents line, because the two fail
independently and a reader needs to know which.

Two rules shape the rest. Nothing is hidden: a check that fails says what it saw,
and a check that itself throws is caught and reported as what it threw, named by
type. Nothing is inferred: every line is something looked at just now, which is
why the processor check drives the part rather than importing it and calling that
a pass.
"""

from __future__ import annotations

import platform
import re
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, override

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Sequence


def _version(where: Path | None = None) -> str:
    """The package version, read out of the file beside this one.

    Read rather than imported. Importing it would go through the package, and a
    package that will not import is one of the things this exists to report.
    """
    found = re.search(
        r"""VERSION\s*[:=][^"']*["']([^"']+)["']""",
        (where or Path(__file__).resolve().parent / "version.py").read_text(),
    )
    return found.group(1) if found else "unknown"


ROOT = Path(__file__).resolve().parent.parent

VERSION = _version()

DOCUMENTS = ROOT / "docs" / "manufacturer"

OLDEST_PYTHON = (3, 12)

READERS = ("pdftoppm", "tesseract")
"""What it takes to read a page of this member's document.

`pdftoppm` renders the page and `tesseract` reads it. `pdftotext` is not enough
here and is not listed: run against the ARM60 datasheet it returns eighty three
characters for eighty three pages.
"""


class Finding:
    """One thing that was looked at, and what was there."""

    __slots__ = ("advice", "detail", "name", "ok")

    name: str
    ok: bool
    detail: str
    advice: str | None

    def __init__(self, name: str, ok: bool, detail: str, advice: str | None = None) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self) -> str:
        """The one-line form, which is what a reader scans."""
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self) -> str:
        """The same, with what to do about it when there is something to do."""
        if self.ok or not self.advice:
            return self.line
        return f"{self.line}\n         {self.advice}"

    @override
    def __repr__(self) -> str:
        return f"<Finding {self.name} {'ok' if self.ok else 'not ok'}>"


def _python() -> Finding:
    return Finding(
        "python",
        sys.version_info[:2] >= OLDEST_PYTHON,
        f"{platform.python_version()} on {platform.system()} {platform.machine()}",
        f"this package needs {OLDEST_PYTHON[0]}.{OLDEST_PYTHON[1]} or newer",
    )


def _package() -> Finding:
    return Finding("package", True, f"arm6 {VERSION}")


def _default_build(name: str) -> Any:
    """Build a part, importing the package here rather than at the top of the file.

    The package is one of the things that can be broken, and a traceback in place
    of a report helps nobody.
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from arm6.core import Cpu

    return Cpu(name, fill=0)


def _processor(name: str, build: Callable[[str], Any] = _default_build) -> Finding:
    """Whether that part builds, resets and runs, saying what stopped it if not.

    It is driven rather than inspected. A part that imports and then refuses to
    execute an instruction is broken in a way that importing it cannot show.

    The reset is part of what is driven rather than a way of getting to the
    interesting bit. It is the one event that reads memory at an address nobody
    chose, writes two banked registers, and forces a mode, so a report that
    stepped an instruction without ever resetting has left the most board-shaped
    thing this package does untested on the machine it exists to diagnose.
    """
    try:
        core = build(name)
        core.reset()
        after = core.registers.pc
        spent = core.step()
    except Exception as trouble:
        return Finding(
            name,
            False,
            f"{type(trouble).__name__}: {trouble}",
            "this is the core failing rather than anything to do with a document;"
            " the line above is what it said",
        )
    return Finding(
        name,
        True,
        f"built, reset to 0x{after:08X}, and stepped, {spent} cycles spent",
    )


def _documents(where: Path = DOCUMENTS) -> Finding:
    """What is in the documents directory, distinguishing empty from absent.

    A directory holding nothing reads as a library to anything that only checks
    the path, and a run over it passes. The two are reported differently here on
    purpose, and neither is a failure: a fresh checkout has no documents and that
    is the normal state.
    """
    if not where.is_dir():
        return Finding(
            "documents",
            True,
            f"{where} is not there, so no quotation can be checked on this machine",
            "none of these documents is redistributable; put your own copies there",
        )
    held = sorted(one.name for one in where.iterdir() if one.is_file())
    return Finding("documents", True, f"{len(held)} in {where}: {', '.join(held) or 'none'}")


def _recogniser(which: Callable[[str], str | None] = shutil.which) -> Finding:
    """Whether this machine can read a page of a document that carries no text layer."""
    absent = [one for one in READERS if which(one) is None]
    if absent:
        return Finding(
            "recogniser",
            False,
            f"{', '.join(absent)} not installed, so no quotation can be checked here",
            "the ARM60 datasheet has no text layer; a page has to be rendered and read",
        )
    return Finding("recogniser", True, f"{', '.join(READERS)} present")


def examine() -> list[Finding]:
    """Everything worth looking at on this machine, in the order a reader wants it."""
    found = [_python(), _package()]
    found.append(_processor("arm60"))
    found.append(_documents())
    found.append(_recogniser())
    return found


def report(found: Sequence[Finding]) -> list[str]:
    """The lines a person pastes into an issue."""
    unwell = [one for one in found if not one.ok]
    lines = [f"arm6 {VERSION} on {platform.python_version()}, {platform.system()}", ""]
    lines.extend(one.report for one in found)
    lines.append("")
    if unwell:
        lines.append(f"  {len(unwell)} of {len(found)} checks did not pass")
    else:
        lines.append(f"  {len(found)} checks, nothing to report")
    return lines


def main(
    argv: Sequence[str] = (),
    examine: Callable[..., Sequence[Finding]] = examine,
    say: Callable[[str], object] = print,
) -> int:
    found = examine()
    for line in report(found):
        say(line)
    return 1 if any(not one.ok for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

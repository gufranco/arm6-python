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
    found = re.search(
        r"""VERSION\s*[:=][^"']*["']([^"']+)["']""",
        (where or Path(__file__).resolve().parent / "version.py").read_text(),
    )
    return found.group(1) if found else "unknown"


ROOT = Path(__file__).resolve().parent.parent


def _reachable(root: Path = ROOT, path: list[str] | None = None) -> bool:
    where = sys.path if path is None else path
    if str(root) in where:
        return False
    where.insert(0, str(root))
    return True


_reachable()

from arm6 import environment  # noqa: E402

VERSION = _version()

DOCUMENTS = ROOT / "docs" / "manufacturer"

OLDEST_PYTHON = (3, 12)

READERS = ("pdftoppm", "tesseract")


class Finding:
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
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self) -> str:
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
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from arm6.core import Cpu

    return Cpu(name, fill=0)


def _processor(name: str, build: Callable[[str], Any] = _default_build) -> Finding:
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
    found = [_python(), _package()]
    found.append(_processor("arm60"))
    found.append(_documents())
    found.append(_recogniser())
    return found


def report(found: Sequence[Finding]) -> list[str]:
    unwell = [one for one in found if not one.ok]
    lines = [f"arm6 {VERSION} on {platform.python_version()}, {platform.system()}", ""]
    lines.append("  the machine")
    lines.extend(environment.lines(ROOT))
    lines.append("")
    lines.append("  this package")
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

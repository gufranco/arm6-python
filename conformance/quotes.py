from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any, NamedTuple, override

ROOT = Path(__file__).resolve().parent.parent

DOCUMENTS = ROOT / "docs" / "manufacturer"

CACHE = DOCUMENTS / ".recognised"

RECORDS = ROOT / "conformance"

WINDOW = 5

BAR = 0.4

RENDER_DPI = "300"


class Claim(NamedTuple):
    where: str
    quote: str
    document: str
    page: int | None


class Verdict(NamedTuple):
    where: str
    quote: str
    document: str
    page: int | None
    placed: int
    windows: int

    @property
    def found(self) -> bool:
        return self.windows > 0 and self.placed / self.windows >= BAR

    @property
    def unchecked(self) -> bool:
        return self.windows == 0

    @override
    def __repr__(self) -> str:
        return f"<Verdict {self.where} {self.placed}/{self.windows}>"


def flatten(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def windows(quote: str) -> list[str]:
    words = quote.split()
    if len(words) < WINDOW:
        return [flatten(quote)]
    return [flatten(" ".join(words[at : at + WINDOW])) for at in range(len(words) - WINDOW + 1)]


def placed(quote: str, body: str) -> tuple[int, int]:
    made = windows(quote)
    flat = flatten(body)
    return sum(1 for one in made if one in flat), len(made)


def _shell(command: Sequence[str], **options: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, **options)  # noqa: PLW1510  # pragma: no cover


def text_layer(path: Path, page: int, run: Callable[..., Any] | None = None) -> str:
    runner = _shell if run is None else run
    try:
        done = runner(
            ["pdftotext", "-layout", "-f", str(page), "-l", str(page), str(path), "-"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return ""
    return str(done.stdout)


def _recognise(path: Path, page: int, run: Callable[..., Any], cache: Path) -> str:
    made = cache / f"page-{page}"
    try:
        run(
            [
                "pdftoppm",
                "-r",
                RENDER_DPI,
                "-gray",
                "-png",
                "-singlefile",
                "-f",
                str(page),
                "-l",
                str(page),
                str(path),
                str(made),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        done = run(
            ["tesseract", f"{made}.png", "stdout", "--psm", "6", "-l", "eng"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return ""
    finally:
        Path(f"{made}.png").unlink(missing_ok=True)
    return str(done.stdout)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def page_text(
    path: Path,
    page: int,
    run: Callable[..., Any] | None = None,
    cache: Path | None = None,
) -> str:
    runner = _shell if run is None else run
    if path.suffix.lower() != ".pdf":
        if not path.exists():
            return ""
        return html.unescape(re.sub(r"<[^>]+>", " ", path.read_text(errors="replace")))

    held = text_layer(path, page, runner)
    if len(flatten(held)) > 40:
        return held

    where = (cache or CACHE) / f"{_digest(path) if path.exists() else 'absent'}-{page}.txt"
    where.parent.mkdir(parents=True, exist_ok=True)
    if where.exists():
        return where.read_text(errors="replace")
    read = _recognise(path, page, runner, where.parent)
    if read.strip():
        where.write_text(read)
    return read


def declared() -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(RECORDS.glob("*.json")):
        collect_documents(json.loads(path.read_text()), found)
    return found


def collect_documents(node: Any, into: dict[str, dict[str, Any]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "documents" and isinstance(value, dict):
                for name, one in value.items():
                    if isinstance(one, dict):
                        into[name] = one
            else:
                collect_documents(value, into)
    elif isinstance(node, list):
        for one in node:
            collect_documents(one, into)


def claims(node: Any, trail: str = "") -> list[Claim]:
    found: list[Claim] = []
    if isinstance(node, dict):
        document = node.get("document")
        page = node.get("page")
        for key, value in node.items():
            step = f"{trail}.{key}" if trail else key
            low = key.lower()
            if low.endswith("quote") and isinstance(value, str):
                found.append(Claim(trail or key, value, str(document), page))
            elif low.endswith("quotes") and isinstance(value, list):
                found.extend(
                    Claim(f"{trail or key}[{at}]", str(one), str(document), page)
                    for at, one in enumerate(value)
                    if isinstance(one, str)
                )
            else:
                found.extend(claims(value, step))
    elif isinstance(node, list):
        for at, one in enumerate(node):
            found.extend(claims(one, f"{trail}[{at}]"))
    return found


def loaded() -> list[Claim]:
    found: list[Claim] = []
    for path in sorted(RECORDS.glob("*.json")):
        found.extend(claims(json.loads(path.read_text()), path.stem))
    return found


def readable(sources: dict[str, dict[str, Any]], where: Path | None = None) -> int:
    at = DOCUMENTS if where is None else where
    return sum(1 for one in sources.values() if (at / str(one.get("file"))).exists())


def verify(
    held: Iterable[Claim] | None = None,
    run: Callable[..., Any] | None = None,
    cache: Path | None = None,
) -> tuple[list[Verdict], int]:
    sources = declared()
    pages: dict[tuple[str, int], str] = {}
    books = readable(sources)
    verdicts = []
    for claim in held if held is not None else loaded():
        source = sources.get(claim.document)
        if source is None or claim.page is None:
            verdicts.append(Verdict(claim.where, claim.quote, claim.document, claim.page, 0, 0))
            continue
        path = DOCUMENTS / str(source.get("file"))
        key = (claim.document, claim.page)
        if key not in pages:
            pages[key] = page_text(path, claim.page, run, cache)
        body = pages[key]
        if not body:
            verdicts.append(Verdict(claim.where, claim.quote, claim.document, claim.page, 0, 0))
            continue
        got, total = placed(claim.quote, body)
        verdicts.append(Verdict(claim.where, claim.quote, claim.document, claim.page, got, total))
    return verdicts, books


def report(found: Sequence[Verdict], books: int) -> list[str]:
    checked = [one for one in found if not one.unchecked]
    lost = [one for one in checked if not one.found]
    lines = [f"  {len(found)} passages in the records, against {books} documents on this machine"]
    if not checked:
        lines.append(
            "  no document here could be read, so nothing was checked."
            " That is the normal state of a fresh checkout: none of these is redistributable."
        )
        return lines
    lines.append(f"  {len(checked) - len(lost)} of {len(checked)} placed on the page they name")
    for one in lost:
        lines.append(f"   ! {one.where}: {one.placed}/{one.windows} windows on page {one.page}")
        lines.append(f"       {one.quote[:96]}")
    if len(found) != len(checked):
        lines.append(f"  {len(found) - len(checked)} could not be checked on this machine")
    return lines


def main(
    argv: Sequence[str] = (),
    check: Callable[[], tuple[list[Verdict], int]] = verify,
    say: Callable[[str], object] = print,
) -> int:
    found, books = check()
    for line in report(found, books):
        say(line)
    return 1 if any(not one.found and not one.unchecked for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

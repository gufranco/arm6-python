"""Look for every sentence the record calls a quote in the document it names.

A record that quotes a document makes a checkable claim, and until something
checks it the sentence is a comment: free to drift, and read as evidence while it
does.

This member needs more machinery than its siblings to do the same job, and the
reason is worth stating rather than discovering. The ARM60 datasheet carries no
text layer at all. Asking `pdftotext` for its contents returns one newline per
page, eighty three characters for eighty three pages. Every other member in this
family reads a document that way, so ported unchanged the checker here would find
nothing, report nothing missing, and exit zero over a document it had not read.

So a page with no text layer is rendered and recognised instead, and the result
is cached beside the document. That makes the check real at the cost of two
external tools, and the doctor reports whether this machine has them.

Matching is deliberately loose. A recogniser misreads perhaps a word in twenty,
so a quote is scored on how many of its five-word windows appear rather than on
an exact search. That survives a misread word and a line break in the middle of
one, and still fails a sentence that was never printed.

The page matters as much as the sentence. Searching the whole document answers
"did somebody print this", not "did the page this record cites print it", and
those come apart exactly when a fact is filed against the wrong source.

The documents are not in this repository and never will be: none is
redistributable. So a run with none on disk checks nothing and says so, rather
than passing quietly.

Usage:
    python3 -m conformance.quotes
"""

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
"""Where a recognised page is kept, keyed by the document's digest and the page.

Beside the documents rather than in the repository, because it is derived from
something the repository is not allowed to carry and belongs on the same machine.
"""

RECORDS = ROOT / "conformance"

WINDOW = 5
"""Words per window. Short enough to survive a misread word, long enough that
matching one is not a coincidence."""

BAR = 0.4
"""The share of windows a quote must place to count as found.

A recogniser misreads perhaps a word in twenty, and a quote of thirty words has
twenty-six windows, so a passing quote usually places most of them. The bar sits
low because the question is whether the sentence is on the page at all, not
whether the recogniser read it well.
"""

RENDER_DPI = "300"


class Claim(NamedTuple):
    """One passage the record attributes to a page of a document."""

    where: str
    quote: str
    document: str
    page: int | None


class Verdict(NamedTuple):
    """One claim, and the best the page it names could do with it."""

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
        """True when there was nothing to check against, which is not a failure."""
        return self.windows == 0

    @override
    def __repr__(self) -> str:
        return f"<Verdict {self.where} {self.placed}/{self.windows}>"


def flatten(text: str) -> str:
    """Everything that is not a letter or a digit, gone, and the rest lowercased.

    That survives hyphenation across a line break, collapsed spaces and
    inconsistent punctuation. It does not survive a homoglyph or a misread digit,
    so a quote that fails to match is a quote to read on the page rather than one
    to delete.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def windows(quote: str) -> list[str]:
    words = quote.split()
    if len(words) < WINDOW:
        return [flatten(quote)]
    return [flatten(" ".join(words[at : at + WINDOW])) for at in range(len(words) - WINDOW + 1)]


def placed(quote: str, body: str) -> tuple[int, int]:
    """How many of a quote's windows the body carries, and how many there were.

    The body is flattened here rather than by the caller, so a caller cannot get
    a false miss by handing over text that had not been through it.
    """
    made = windows(quote)
    flat = flatten(body)
    return sum(1 for one in made if one in flat), len(made)


def _shell(command: Sequence[str], **options: Any) -> subprocess.CompletedProcess[str]:
    """The real shell, with the same signature the injected stand-ins have.

    Marked no-cover because running it would run the external tools, which is
    what the check itself does and not what a test of the check should do.
    """
    return subprocess.run(command, **options)  # noqa: PLW1510  # pragma: no cover


def text_layer(path: Path, page: int, run: Callable[..., Any] | None = None) -> str:
    """What the document's own text layer says about one page, if it has one.

    A machine without the reader is the same case as a machine without the
    document: nothing to check against, reported rather than thrown.
    """
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
    """Render one page and read it, which is the only way into this document.

    `-singlefile` is not a tidiness choice. Without it `pdftoppm` names its output
    after the page and zero-pads the number to the width of the document's page
    count, so page 4 of an eighty three page document lands in `page-04.png` and a
    reader looking for `page-4.png` finds nothing. That failure is silent: the
    page reads as empty, every quotation cited to it is reported as unchecked
    rather than as missing, and the run still exits zero. It cost nine of this
    record's fifty passages before it was found.
    """
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
    """One page of a document, however that document has to be read.

    A document that is not a scan is read as it stands. One that is, and that
    carries a usable text layer, is read through it. One that carries none is
    rendered and recognised, and the result is kept so the next run is cheap.
    """
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
    """Every document the records name, keyed the way a citation names it."""
    found: dict[str, dict[str, Any]] = {}
    for path in sorted(RECORDS.glob("*.json")):
        _collect_documents(json.loads(path.read_text()), found)
    return found


def _collect_documents(node: Any, into: dict[str, dict[str, Any]]) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "documents" and isinstance(value, dict):
                for name, one in value.items():
                    if isinstance(one, dict):
                        into[name] = one
            else:
                _collect_documents(value, into)
    elif isinstance(node, list):
        for one in node:
            _collect_documents(one, into)


def claims(node: Any, trail: str = "") -> list[Claim]:
    """Every passage a record calls a quote, with the page it names.

    Only keys ending in `quote` or `quotes` count. That is the whole rule, and it
    is why a passage filed under any other name is a document's words that
    nothing holds to the document.
    """
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
    """Every claim in every record here."""
    found: list[Claim] = []
    for path in sorted(RECORDS.glob("*.json")):
        found.extend(claims(json.loads(path.read_text()), path.stem))
    return found


def readable(sources: dict[str, dict[str, Any]]) -> int:
    """How many of the declared documents are on this machine.

    A count rather than a boolean, because the report has to be able to say that
    it looked at three documents and found none, which is a different sentence
    from having looked at nothing.
    """
    return sum(1 for one in sources.values() if (DOCUMENTS / str(one.get("file"))).exists())


def verify(
    held: Iterable[Claim] | None = None,
    run: Callable[..., Any] | None = None,
    cache: Path | None = None,
) -> tuple[list[Verdict], int]:
    """Every claim against the page it names, and how many documents were readable."""
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
    """What was examined, and when the answer is nothing, that rather than nothing."""
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

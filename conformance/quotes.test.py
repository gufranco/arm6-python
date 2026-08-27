"""That the quote checker checks, and reports what it could not check.

Every sentence the record attributes to a document is a claim that can be held to
that document, and until something holds it there it is a comment: free to drift,
and read as evidence while it does.

This member's document makes that harder than usual and the checker harder to
trust. The ARM60 datasheet carries no text layer, so the way every other member
reads a document returns nothing here, and an absence that means nothing looks
exactly like an absence that means everything. So the reading path is checked
here against runners the test controls, including one that returns nothing at
all.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import quotes  # noqa: E402


def runner(**answers: str) -> Any:
    """A stand-in for the shell, answering by which tool was asked for."""

    def run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        tool = Path(command[0]).name
        return subprocess.CompletedProcess(command, 0, stdout=answers.get(tool, ""), stderr="")

    return run


def refusing() -> Any:
    def run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError(command[0])

    return run


class FlatteningTest(unittest.TestCase):
    def test_punctuation_and_case_are_dropped(self) -> None:
        held = quotes.flatten("The C flag, set to a MEANINGLESS value.")

        self.assertEqual(held, "thecflagsettoameaninglessvalue")

    def test_a_line_break_inside_a_word_survives_it(self) -> None:
        held = quotes.flatten("meaning-\nless")

        self.assertEqual(held, "meaningless")

    def test_a_run_of_five_words_is_one_window(self) -> None:
        held = quotes.windows("one two three four five")

        self.assertEqual(len(held), 1)

    def test_a_longer_passage_gives_one_window_per_starting_word(self) -> None:
        held = quotes.windows("one two three four five six seven")

        self.assertEqual(len(held), 3)

    def test_a_passage_shorter_than_a_window_is_matched_whole(self) -> None:
        held = quotes.windows("two words")

        self.assertEqual(held, ["twowords"])


class ScoringTest(unittest.TestCase):
    def test_a_passage_that_is_there_places_every_window(self) -> None:
        held = quotes.placed("the quick brown fox jumps", "before the quick brown fox jumps after")

        self.assertEqual(held, (1, 1))

    def test_a_passage_that_is_not_places_none(self) -> None:
        held = quotes.placed("the quick brown fox jumps", "nothing of the sort appears here")

        self.assertEqual(held[0], 0)

    def test_a_passage_with_one_misread_word_still_places_most_of_it(self) -> None:
        body = quotes.flatten("the quick brown fox jumps over the lazy dog today")
        held = quotes.placed("the quick brown fox jumps over the 1azy dog today", body)

        self.assertGreater(held[0] / held[1], quotes.BAR)

    def test_a_passage_that_was_never_printed_falls_below_the_bar(self) -> None:
        body = quotes.flatten("the quick brown fox jumps over the lazy dog")
        held = quotes.placed("this sentence appears in no document at all anywhere", body)

        self.assertLess(held[0] / held[1], quotes.BAR)


class ReadingADocumentTest(unittest.TestCase):
    def test_a_document_with_a_text_layer_is_read_through_it(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            held = quotes.text_layer(
                Path(where) / "a.pdf", 1, run=runner(pdftotext="a real sentence on the page")
            )

            self.assertIn("real sentence", held)

    def test_a_document_with_no_text_layer_reads_as_empty(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            held = quotes.text_layer(Path(where) / "a.pdf", 1, run=runner(pdftotext="\n"))

            self.assertEqual(held.strip(), "")

    def test_a_machine_without_the_reader_reports_nothing_rather_than_throwing(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            held = quotes.text_layer(Path(where) / "a.pdf", 1, run=refusing())

            self.assertEqual(held, "")

    def test_a_page_with_no_text_layer_is_rendered_and_recognised(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            held = quotes.page_text(
                Path(where) / "a.pdf",
                1,
                run=runner(pdftotext="\n", tesseract="the recognised sentence"),
                cache=Path(where),
            )

            self.assertIn("recognised", held)

    def test_a_page_that_has_one_is_not_rendered_at_all(self) -> None:
        asked: list[str] = []

        def watching(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
            asked.append(Path(command[0]).name)
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="a genuine sentence long enough to be a real text layer",
                stderr="",
            )

        with tempfile.TemporaryDirectory() as where:
            quotes.page_text(Path(where) / "a.pdf", 1, run=watching, cache=Path(where))

            self.assertNotIn("tesseract", asked)

    def test_a_recognised_page_is_kept_so_the_next_run_is_cheap(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            quotes.page_text(
                Path(where) / "a.pdf",
                1,
                run=runner(pdftotext="\n", tesseract="recognised once"),
                cache=Path(where),
            )

            held = list(Path(where).glob("*.txt"))
            self.assertEqual(len(held), 1)

    def test_and_the_second_run_reads_the_cache_rather_than_the_recogniser(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            quotes.page_text(
                Path(where) / "a.pdf",
                1,
                run=runner(pdftotext="\n", tesseract="recognised once"),
                cache=Path(where),
            )

            held = quotes.page_text(Path(where) / "a.pdf", 1, run=refusing(), cache=Path(where))

            self.assertIn("recognised once", held)

    def test_a_document_that_is_not_a_pdf_is_read_as_it_stands(self) -> None:
        with tempfile.TemporaryDirectory() as where:
            page = Path(where) / "a.html"
            page.write_text("<p>the sentence in the note</p>")

            held = quotes.page_text(page, 1, run=refusing(), cache=Path(where))

            self.assertIn("sentence in the note", held)


class WhatTheRecordClaimsTest(unittest.TestCase):
    def test_every_passage_under_a_quote_key_is_collected(self) -> None:
        record = {"facts": {"one": {"quote": "a sentence", "document": "d", "page": 1}}}

        held = quotes.claims(record)

        self.assertEqual(len(held), 1)

    def test_a_passage_under_any_other_key_is_not_a_quote(self) -> None:
        record = {"facts": {"one": {"note": "a sentence", "document": "d", "page": 1}}}

        held = quotes.claims(record)

        self.assertEqual(held, [])

    def test_a_numbered_set_of_passages_is_collected_too(self) -> None:
        record = {"facts": {"one": {"quotes": ["first", "second"], "document": "d", "page": 1}}}

        held = quotes.claims(record)

        self.assertEqual(len(held), 2)

    def test_a_claim_carries_the_document_and_page_it_names(self) -> None:
        record = {"facts": {"one": {"quote": "a sentence", "document": "d", "page": 7}}}

        held = quotes.claims(record)

        self.assertEqual((held[0].document, held[0].page), ("d", 7))

    def test_a_record_that_quotes_nothing_yields_nothing(self) -> None:
        held = quotes.claims({"note": "no passages here"})

        self.assertEqual(held, [])

    def test_this_repository_s_own_record_carries_claims(self) -> None:
        held = quotes.loaded()

        self.assertGreater(len(held), 20)

    def test_and_every_one_of_them_names_a_declared_document(self) -> None:
        declared = set(quotes.declared())

        stray = sorted({one.document for one in quotes.loaded()} - declared)

        self.assertEqual(stray, [])

    def test_and_every_one_of_them_names_a_page(self) -> None:
        silent = [one.where for one in quotes.loaded() if one.page is None]

        self.assertEqual(silent, [])


class TheVerdictTest(unittest.TestCase):
    def test_a_placed_passage_reads_as_found(self) -> None:
        held = quotes.Verdict("where", "a sentence", "d", 1, 4, 4)

        self.assertTrue(held.found)

    def test_a_passage_that_placed_nothing_does_not(self) -> None:
        held = quotes.Verdict("where", "a sentence", "d", 1, 0, 4)

        self.assertFalse(held.found)

    def test_a_passage_with_no_document_on_this_machine_is_neither(self) -> None:
        held = quotes.Verdict("where", "a sentence", "d", 1, 0, 0)

        self.assertTrue(held.unchecked)

    def test_a_verdict_says_what_it_was_when_printed(self) -> None:
        held = repr(quotes.Verdict("where", "a sentence", "d", 1, 4, 4))

        self.assertIn("where", held)


class TheReportTest(unittest.TestCase):
    def test_a_run_that_checked_nothing_says_so_rather_than_passing_quietly(self) -> None:
        held = quotes.report([quotes.Verdict("w", "q", "d", 1, 0, 0)], books=0)

        self.assertIn("no document", "\n".join(held))

    def test_a_run_that_placed_everything_says_how_many(self) -> None:
        held = quotes.report([quotes.Verdict("w", "q", "d", 1, 4, 4)], books=1)

        self.assertIn("1 of 1", "\n".join(held))

    def test_a_run_with_a_passage_it_could_not_place_names_it(self) -> None:
        held = quotes.report([quotes.Verdict("theFact", "q", "d", 1, 0, 4)], books=1)

        self.assertIn("theFact", "\n".join(held))

    def test_a_clean_run_exits_zero(self) -> None:
        held = quotes.main(
            [], check=lambda: ([quotes.Verdict("w", "q", "d", 1, 4, 4)], 1), say=lambda _: None
        )

        self.assertEqual(held, 0)

    def test_a_run_with_a_passage_it_could_not_place_exits_one(self) -> None:
        held = quotes.main(
            [], check=lambda: ([quotes.Verdict("w", "q", "d", 1, 0, 4)], 1), say=lambda _: None
        )

        self.assertEqual(held, 1)

    def test_a_run_with_no_documents_exits_zero_and_says_it_checked_nothing(self) -> None:
        said: list[str] = []

        held = quotes.main(
            [], check=lambda: ([quotes.Verdict("w", "q", "d", 1, 0, 0)], 0), say=said.append
        )

        self.assertEqual((held, "no document" in "\n".join(said)), (0, True))


class DrivenAgainstSomethingThatShouldFailTest(unittest.TestCase):
    """A check nobody has seen fail is not known to work.

    Two failures matter and they are different. A sentence nobody printed must
    not place. And a sentence that was printed, filed under the wrong page, must
    not place either: that is the failure a checker which searched the whole
    document would miss, and it is the one that happens when a fact is recorded
    against the wrong source.
    """

    def test_a_sentence_that_was_never_printed_does_not_place(self) -> None:
        body = quotes.flatten("the page says something else entirely")

        held = quotes.placed("ARM60 contains a single cycle hardware divider", body)

        self.assertLess(held[0] / held[1], quotes.BAR)

    def test_a_real_sentence_filed_under_the_wrong_page_does_not_place(self) -> None:
        wrong = quotes.flatten("this page carries the pinout and nothing else")

        held = quotes.placed("A MUL will give a zero result if Rm=Rd", wrong)

        self.assertLess(held[0] / held[1], quotes.BAR)


class TheRecordIsWellFormedTest(unittest.TestCase):
    def test_every_declared_document_names_the_file_it_is(self) -> None:
        silent = [key for key, one in quotes.declared().items() if not one.get("file")]

        self.assertEqual(silent, [])

    def test_and_carries_a_digest_so_a_reader_can_confirm_the_scan(self) -> None:
        silent = [key for key, one in quotes.declared().items() if not one.get("sha256")]

        self.assertEqual(silent, [])

    def test_the_record_parses(self) -> None:
        held = json.loads((ROOT / "conformance" / "hardware.json").read_text())

        self.assertIn("documents", held)


if __name__ == "__main__":
    unittest.main(verbosity=2)

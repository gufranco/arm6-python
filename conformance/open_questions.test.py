"""That the open questions document names every question that is actually open.

A file like this is worth having only while it is complete. One divergence added
to the record and not to the document, and the document quietly becomes a claim
that the project knows more than it does, which is the failure it exists to
prevent.
"""

import json
import sys
import unittest
from pathlib import Path
from typing import Any, override

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DOCUMENT = ROOT / "OPEN-QUESTIONS.md"

RECORD = ROOT / "conformance" / "divergences.json"

STANDINGS = ("open", "closed", "notADisagreement")


def divergences() -> list[dict[str, Any]]:
    held: list[dict[str, Any]] = json.loads(RECORD.read_text())["divergences"]
    return held


def opened() -> list[dict[str, Any]]:
    return [one for one in divergences() if one["status"] == "open"]


class RecordTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.text = DOCUMENT.read_text()

    def test_every_divergence_says_where_it_stands(self) -> None:
        stray = [one["id"] for one in divergences() if one.get("status") not in STANDINGS]

        self.assertEqual(stray, [])

    def test_every_divergence_names_the_heading_that_carries_it(self) -> None:
        silent = [one["id"] for one in divergences() if not one.get("topic")]

        self.assertEqual(silent, [])

    def test_the_document_names_every_open_one(self) -> None:
        missing = [one["id"] for one in opened() if one["topic"] not in self.text]

        self.assertEqual(missing, [])

    def test_and_every_one_this_project_declines_to_model(self) -> None:
        missing = [
            one["id"]
            for one in divergences()
            if one["status"] == "notADisagreement" and one["topic"] not in self.text
        ]

        self.assertEqual(missing, [])

    def test_and_names_none_that_are_closed(self) -> None:
        named = [
            one["id"]
            for one in divergences()
            if one["status"] == "closed" and one["topic"] in self.text
        ]

        self.assertEqual(named, [])

    def test_each_open_one_says_what_this_project_follows(self) -> None:
        silent = [one["id"] for one in opened() if not one.get("packageFollows")]

        self.assertEqual(silent, [])

    def test_and_what_would_settle_it(self) -> None:
        silent = [one["id"] for one in opened() if not one.get("wouldSettleIt")]

        self.assertEqual(silent, [])

    def test_the_document_says_what_is_not_in_question(self) -> None:
        self.assertIn("What is not in question", self.text)

    def test_and_separates_what_is_unknown_from_what_is_absent_on_purpose(self) -> None:
        self.assertIn("What is deliberately not modelled", self.text)

    def test_there_are_open_questions_to_report(self) -> None:
        self.assertEqual(len(opened()), 10)

    def test_and_the_record_says_where_they_are_written_up(self) -> None:
        held = json.loads(RECORD.read_text())

        self.assertIn("OPEN-QUESTIONS.md", held["writtenUpIn"])


if __name__ == "__main__":
    unittest.main()

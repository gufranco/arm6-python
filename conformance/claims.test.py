from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import quotes  # noqa: E402


class WhatTheRecordClaimsTest(unittest.TestCase):
    def test_every_passage_under_a_quote_key_is_collected(self) -> None:
        # Arrange
        record = {"facts": {"one": {"quote": "a sentence", "document": "d", "page": 1}}}

        # Act
        held = quotes.claims(record)

        # Assert
        self.assertEqual(len(held), 1)

    def test_a_passage_under_any_other_key_is_not_a_quote(self) -> None:
        # Arrange
        record = {"facts": {"one": {"note": "a sentence", "document": "d", "page": 1}}}

        # Act
        held = quotes.claims(record)

        # Assert
        self.assertEqual(held, [])

    def test_a_numbered_set_of_passages_is_collected_too(self) -> None:
        # Arrange
        record = {"facts": {"one": {"quotes": ["first", "second"], "document": "d", "page": 1}}}

        # Act
        held = quotes.claims(record)

        # Assert
        self.assertEqual(len(held), 2)

    def test_a_claim_carries_the_document_and_page_it_names(self) -> None:
        # Arrange
        record = {"facts": {"one": {"quote": "a sentence", "document": "d", "page": 7}}}

        # Act
        held = quotes.claims(record)

        # Assert
        self.assertEqual((held[0].document, held[0].page), ("d", 7))

    def test_a_record_that_quotes_nothing_yields_nothing(self) -> None:
        # Arrange
        record = {"note": "no passages here"}

        # Act
        held = quotes.claims(record)

        # Assert
        self.assertEqual(held, [])

    def test_this_repository_s_own_record_carries_claims(self) -> None:
        # Arrange
        enough = 20

        # Act
        held = quotes.loaded()

        # Assert
        self.assertGreater(len(held), enough)

    def test_and_every_one_of_them_names_a_declared_document(self) -> None:
        # Arrange
        declared = set(quotes.declared())

        # Act
        held = quotes.loaded()

        # Assert
        stray = sorted({one.document for one in held} - declared)
        self.assertEqual(stray, [])

    def test_and_every_one_of_them_names_a_page(self) -> None:
        # Arrange
        unpaged = None

        # Act
        held = quotes.loaded()

        # Assert
        silent = [one.where for one in held if one.page is unpaged]
        self.assertEqual(silent, [])


class TheRecordIsWellFormedTest(unittest.TestCase):
    def test_every_declared_document_names_the_file_it_is(self) -> None:
        # Arrange
        field = "file"

        # Act
        held = quotes.declared()

        # Assert
        silent = [key for key, one in held.items() if not one.get(field)]
        self.assertEqual(silent, [])

    def test_and_carries_a_digest_so_a_reader_can_confirm_the_scan(self) -> None:
        # Arrange
        field = "sha256"

        # Act
        held = quotes.declared()

        # Assert
        silent = [key for key, one in held.items() if not one.get(field)]
        self.assertEqual(silent, [])

    def test_the_record_parses(self) -> None:
        # Arrange
        record = (ROOT / "conformance" / "hardware.json").read_text()

        # Act
        held = json.loads(record)

        # Assert
        self.assertIn("documents", held)


class ReadingTheRecordsTest(unittest.TestCase):
    def test_a_documents_block_inside_a_list_is_found(self) -> None:
        # Arrange
        into: dict[str, Any] = {}

        # Act
        quotes.collect_documents([{"documents": {"a": {"file": "a.pdf"}}}], into)

        # Assert
        self.assertEqual(into, {"a": {"file": "a.pdf"}})

    def test_a_documents_block_that_is_not_a_mapping_is_stepped_over(self) -> None:
        # Arrange
        into: dict[str, Any] = {}

        # Act
        quotes.collect_documents({"documents": "not a block"}, into)

        # Assert
        self.assertEqual(into, {})

    def test_an_entry_that_is_not_a_mapping_is_stepped_over(self) -> None:
        # Arrange
        into: dict[str, Any] = {}

        # Act
        quotes.collect_documents({"documents": {"a": "not an entry"}}, into)

        # Assert
        self.assertEqual(into, {})

    def test_a_quote_inside_a_list_is_collected(self) -> None:
        # Arrange
        record = [{"facts": {"one": {"quote": "a sentence", "document": "d"}}}]

        # Act
        held = quotes.claims(record)

        # Assert
        self.assertEqual(len(held), 1)

    def test_a_numbered_set_holding_something_that_is_not_a_passage_is_stepped_over(
        self,
    ) -> None:
        # Arrange
        record = {"one": {"quotes": [1, 2], "document": "d", "page": 1}}

        # Act
        held = quotes.claims(record)

        # Assert
        self.assertEqual(held, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)

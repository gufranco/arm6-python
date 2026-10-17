from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import printed  # noqa: E402

RECORD = json.loads((ROOT / "conformance" / "hardware.json").read_text())


class TheFactsOfEveryPartAreReadTest(unittest.TestCase):
    def test_every_fact_of_every_part_is_found_by_its_key(self) -> None:
        # Arrange
        recorded = [name for part in RECORD["parts"] for name in part["facts"]]

        # Act
        found = sorted(printed.facts())

        # Assert
        self.assertEqual(found, sorted(recorded))

    def test_a_fact_s_value_is_the_one_the_record_gives(self) -> None:
        # Arrange
        recorded = RECORD["parts"][0]["facts"]["registerCount"]["value"]

        # Act
        found = printed.value("registerCount")

        # Assert
        self.assertEqual(found, recorded)

    def test_a_fact_s_quote_is_the_sentence_the_record_gives(self) -> None:
        # Arrange
        recorded = RECORD["parts"][0]["facts"]["lslZero"]["quote"]

        # Act
        found = printed.quote("lslZero")

        # Assert
        self.assertEqual(found, recorded)

    def test_a_key_the_record_does_not_hold_is_refused(self) -> None:
        # Arrange
        missing = "notAFact"

        # Act
        with self.assertRaises(KeyError) as refused:
            printed.quote(missing)

        # Assert
        self.assertEqual(refused.exception.args, (missing,))


if __name__ == "__main__":
    unittest.main(verbosity=2)

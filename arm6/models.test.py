"""That the catalogue is published even though it holds one part today.

A member covering one part is the tempting exception to the family's rule that
every part publishes a catalogue, and it is the worst one: a caller who learns to
leave the model out here writes the same call against a member covering sixteen
and gets a part nobody picked. So the model is required, there is no default, and
a name no model answers to is refused with every model there is listed.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6.errors import UnknownModelError  # noqa: E402
from arm6.models import MODELS, Model, resolve  # noqa: E402


class TheCatalogueTest(unittest.TestCase):
    def test_it_holds_the_one_part_a_document_was_found_for(self) -> None:
        held = sorted(MODELS)

        self.assertEqual(held, ["arm60"])

    def test_the_part_knows_its_own_name(self) -> None:
        held = MODELS["arm60"].name

        self.assertEqual(held, "arm60")

    def test_the_part_says_what_it_is_when_printed(self) -> None:
        held = repr(MODELS["arm60"])

        self.assertEqual(held, "Model('arm60')")

    def test_every_entry_is_a_model(self) -> None:
        held = {type(one) for one in MODELS.values()}

        self.assertEqual(held, {Model})

    def test_the_part_carries_a_summary_a_reader_can_use(self) -> None:
        held = MODELS["arm60"].summary

        self.assertIn("32", held)


class NamingOneIsNotOptionalTest(unittest.TestCase):
    def test_a_name_the_catalogue_holds_resolves_to_that_part(self) -> None:
        held = resolve("arm60")

        self.assertIs(held, MODELS["arm60"])

    def test_a_name_in_any_case_resolves_to_the_same_part(self) -> None:
        held = resolve("ARM60")

        self.assertIs(held, MODELS["arm60"])

    def test_an_alias_the_part_answers_to_resolves_as_well(self) -> None:
        held = resolve("arm6")

        self.assertIs(held, MODELS["arm60"])

    def test_a_name_no_model_goes_by_is_refused(self) -> None:
        with self.assertRaises(UnknownModelError):
            resolve("arm610")

    def test_and_the_refusal_lists_every_model_there_is(self) -> None:
        with self.assertRaises(UnknownModelError) as caught:
            resolve("arm610")

        self.assertIn("arm60", str(caught.exception))

    def test_naming_none_is_refused_too(self) -> None:
        with self.assertRaises(UnknownModelError):
            resolve("")

    def test_and_that_refusal_lists_them_as_well(self) -> None:
        with self.assertRaises(UnknownModelError) as caught:
            resolve("")

        self.assertIn("arm60", str(caught.exception))

    def test_a_name_that_is_not_a_string_is_refused_rather_than_coerced(self) -> None:
        with self.assertRaises(UnknownModelError):
            resolve(None)


class TheAliasesTest(unittest.TestCase):
    def test_the_part_answers_to_the_family_name_as_well_as_its_own(self) -> None:
        held = sorted(MODELS["arm60"].aliases)

        self.assertEqual(held, ["arm6"])

    def test_no_alias_collides_with_another_model_s_name(self) -> None:
        names = set(MODELS)

        clashing = [one for model in MODELS.values() for one in model.aliases if one in names]

        self.assertEqual(clashing, [])


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_a_model_refuses_a_name_it_does_not_have(self) -> None:
        held = MODELS["arm60"]

        with self.assertRaises(AttributeError):
            held.q = 1


if __name__ == "__main__":
    unittest.main(verbosity=2)

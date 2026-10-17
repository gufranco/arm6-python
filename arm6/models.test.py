from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import MODELS, Cpu, Model, UnknownModelError  # noqa: E402
from conformance.printed import quote  # noqa: E402


class TheCatalogueTest(unittest.TestCase):
    def test_it_holds_the_one_part_a_document_was_found_for(self) -> None:
        # Arrange
        catalogue = MODELS

        # Act
        held = sorted(catalogue)

        # Assert
        self.assertEqual(held, ["arm60"])

    def test_the_part_knows_its_own_name(self) -> None:
        # Arrange
        part = Cpu("arm60")

        # Act
        held = part.model.name

        # Assert
        self.assertEqual(held, "arm60")

    def test_the_part_says_what_it_is_when_printed(self) -> None:
        # Arrange
        model = Cpu("arm60").model

        # Act
        held = repr(model)

        # Assert
        self.assertEqual(held, "Model('arm60')")

    def test_every_entry_is_a_model(self) -> None:
        # Arrange
        catalogue = MODELS

        # Act
        held = {type(one) for one in catalogue.values()}

        # Assert
        self.assertEqual(held, {Model})

    def test_the_part_carries_a_summary_a_reader_can_use(self) -> None:
        # Arrange
        part = Cpu("arm60")

        # Act
        held = part.model.summary

        # Assert
        self.assertIn("32 bit address bus", held)


class NamingOneIsNotOptionalTest(unittest.TestCase):
    def test_a_name_the_catalogue_holds_resolves_to_that_part(self) -> None:
        # Arrange
        name = "arm60"

        # Act
        held = Cpu(name).model

        # Assert
        self.assertIs(held, MODELS["arm60"])

    def test_a_name_in_any_case_resolves_to_the_same_part(self) -> None:
        # Arrange
        name = "ARM60"

        # Act
        held = Cpu(name).model

        # Assert
        self.assertIs(held, MODELS["arm60"])

    def test_an_alias_the_part_answers_to_resolves_as_well(self) -> None:
        # Arrange
        name = "arm6"

        # Act
        held = Cpu(name).model

        # Assert
        self.assertIs(held, MODELS["arm60"])

    def test_a_name_no_model_goes_by_is_refused(self) -> None:
        # Arrange
        name = "arm610"

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Cpu(name)

        # Assert
        self.assertIn("'arm610' is not a model", str(caught.exception))

    def test_and_the_refusal_lists_every_model_there_is(self) -> None:
        # Arrange
        name = "arm610"

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Cpu(name)

        # Assert
        self.assertTrue(str(caught.exception).endswith("arm6, arm60"))

    def test_naming_none_is_refused_too(self) -> None:
        # Arrange
        name = ""

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Cpu(name)

        # Assert
        self.assertTrue(str(caught.exception).startswith("name a model"))

    def test_and_that_refusal_lists_them_as_well(self) -> None:
        # Arrange
        name = ""

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Cpu(name)

        # Assert
        self.assertIn("arm6, arm60", str(caught.exception))

    def test_a_name_that_is_not_a_string_is_refused_rather_than_coerced(self) -> None:
        # Arrange
        name = None

        # Act
        with self.assertRaises(UnknownModelError) as caught:
            Cpu(name)  # type: ignore[arg-type]

        # Assert
        self.assertIn("arm6, arm60", str(caught.exception))


class TheAliasesTest(unittest.TestCase):
    def test_the_part_answers_to_the_family_name_as_well_as_its_own(self) -> None:
        # Arrange
        model = MODELS["arm60"]

        # Act
        held = sorted(model.aliases)

        # Assert
        self.assertEqual(held, ["arm6"], quote("coreIsTheArm6"))

    def test_no_alias_collides_with_another_model_s_name(self) -> None:
        # Arrange
        names = set(MODELS)

        # Act
        clashing = [one for model in MODELS.values() for one in model.aliases if one in names]

        # Assert
        self.assertEqual(clashing, [])


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_a_model_refuses_a_name_it_does_not_have(self) -> None:
        # Arrange
        held = MODELS["arm60"]

        # Act
        with self.assertRaises(AttributeError) as caught:
            held.q = 1

        # Assert
        self.assertIn("catalogue entry", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

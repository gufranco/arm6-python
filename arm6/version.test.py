"""That the package publishes a version and builds a part the family way."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import arm6
from arm6 import version


class ConstructionTest(unittest.TestCase):
    def test_a_processor_is_built_from_the_name_of_a_part(self) -> None:
        held = arm6.Cpu("arm60")

        self.assertEqual(held.model.name, "arm60")

    def test_options_reach_the_processor_that_gets_built(self) -> None:
        held = arm6.Cpu("arm60", fill=0)

        self.assertEqual(held.registers.read(0), 0)

    def test_the_part_handed_back_carries_the_kind_s_name(self) -> None:
        held = type(arm6.Cpu("arm60")).__name__

        self.assertEqual(held, "Cpu")


class VersionTest(unittest.TestCase):
    def test_the_package_carries_a_version(self) -> None:
        self.assertTrue(version.VERSION)

    def test_and_publishes_it_the_way_python_expects(self) -> None:
        self.assertEqual(arm6.__version__, version.VERSION)


if __name__ == "__main__":
    unittest.main(verbosity=2)

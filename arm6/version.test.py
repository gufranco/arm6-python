from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402

STAMPED = re.compile(r'^VERSION = "(\d+\.\d+\.\d+)"$', re.MULTILINE)


class ConstructionTest(unittest.TestCase):
    def test_a_processor_is_built_from_the_name_of_a_part(self) -> None:
        # Arrange
        name = "arm60"

        # Act
        held = arm6.Cpu(name)

        # Assert
        self.assertEqual(held.model.name, "arm60")

    def test_options_reach_the_processor_that_gets_built(self) -> None:
        # Arrange
        fill = 0

        # Act
        held = arm6.Cpu("arm60", fill=fill)

        # Assert
        self.assertEqual(held.registers.read(0), 0)

    def test_the_part_handed_back_carries_the_kind_s_name(self) -> None:
        # Arrange
        name = "arm60"

        # Act
        held = type(arm6.Cpu(name)).__name__

        # Assert
        self.assertEqual(held, "Cpu")


class VersionTest(unittest.TestCase):
    def test_the_package_carries_a_version_in_three_numbered_parts(self) -> None:
        # Arrange
        package = arm6

        # Act
        held = package.__version__

        # Assert
        self.assertRegex(held, r"^\d+\.\d+\.\d+$")

    def test_and_publishes_the_one_the_release_job_stamped(self) -> None:
        # Arrange
        stamped = STAMPED.search((ROOT / "arm6" / "version.py").read_text())

        # Act
        held = arm6.__version__

        # Assert
        self.assertEqual(held, stamped.group(1) if stamped else None)


if __name__ == "__main__":
    unittest.main(verbosity=2)

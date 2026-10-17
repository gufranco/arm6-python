from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402
from conformance.printed import quote  # noqa: E402

MUL_R0_R1_R2 = 0xE0000291


def multiplying(multiplier: int) -> arm6.Cpu:
    image = MUL_R0_R1_R2.to_bytes(4, "little")
    held = arm6.Cpu("arm60", arm6.Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    held.registers.write(1, 3)
    held.registers.write(2, multiplier)
    return held


def stepped(parts: list[arm6.Cpu]) -> list[int]:
    return [one.step() for one in parts]


class TheBoothCycleCountTest(unittest.TestCase):
    def test_each_multiplier_takes_the_internal_cycles_its_band_gives(self) -> None:
        # Arrange
        bands = {0: 1, 1: 1, 2: 2, 7: 2, 8: 3, 31: 3, 1 << 29: 16, 0xFFFFFFFF: 16}
        parts = [multiplying(one) for one in bands]

        # Act
        stepped(parts)

        # Assert
        self.assertEqual([one.spent.i for one in parts], list(bands.values()))

    def test_every_band_the_formula_names_is_two_bits_wide(self) -> None:
        # Arrange
        parts = [multiplying(one) for one in range(1 << 27, 1 << 29, 1 << 23)]

        # Act
        stepped(parts)

        # Assert
        self.assertEqual({one.spent.i for one in parts}, {15}, quote("multiplierRadix"))

    def test_the_count_never_exceeds_the_stated_worst_case(self) -> None:
        # Arrange
        parts = [multiplying((1 << width) - 1) for width in range(33)]

        # Act
        stepped(parts)

        # Assert
        self.assertEqual(max(one.spent.i for one in parts), 16)

    def test_a_multiply_spends_one_sequential_cycle_beside_the_internal_ones(self) -> None:
        # Arrange
        held = multiplying(8)

        # Act
        held.step()

        # Assert
        self.assertEqual((held.spent.s, held.spent.n, held.spent.c), (1, 0, 0))

    def test_the_bands_the_datasheet_states_are_the_bands_it_gives(self) -> None:
        # Arrange
        parts = [multiplying(1 << (2 * m - 3)) for m in range(2, 16)]

        # Act
        stepped(parts)

        # Assert
        held = [one.spent.i for one in parts]
        self.assertEqual(held, list(range(2, 16)), quote("multiplyEarlyTermination"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

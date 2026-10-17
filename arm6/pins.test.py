from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import (  # noqa: E402
    MODES,
    Cpu,
    Memory,
)
from conformance.printed import quote  # noqa: E402

MOV_R0_R1 = 0xE1A00001
MOV_R0_R1_LSL_R2 = 0xE1A00211
BRANCH = 0xEA000000
STORE_R0_TO_R1 = 0xE5810000
SWAP_WORD = 0xE1020091
MULTIPLY = 0xE0000291
MODE_FIELD = 0b11111


def machine(*words: int) -> Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


class TheRegisterShiftCycleTheTablesDisagreeAboutTest(unittest.TestCase):
    def test_the_per_cycle_table_makes_the_extra_cycle_internal(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1_LSL_R2)

        # Act
        held.step()

        # Assert
        self.assertEqual((held.spent.s, held.spent.i), (1, 1))

    def test_which_is_the_shape_the_shortest_multiply_has(self) -> None:
        # Arrange
        multiplied = machine(MULTIPLY)
        multiplied.step()
        shifted = machine(MOV_R0_R1_LSL_R2)

        # Act
        shifted.step()

        # Assert
        self.assertEqual(
            [one.kind.letter for one in shifted.bus.cycles],
            [one.kind.letter for one in multiplied.bus.cycles],
        )


class WhatTheBusActuallyDroveTest(unittest.TestCase):
    def test_a_branch_drives_the_prefetch_then_the_destination_then_the_next(self) -> None:
        # Arrange
        held = machine(BRANCH)

        # Act
        held.step()

        # Assert
        self.assertEqual([one.address for one in held.bus.cycles], [8, 8, 12])

    def test_a_store_drives_the_address_it_computed_with_the_write_line_high(self) -> None:
        # Arrange
        held = machine(STORE_R0_TO_R1)
        held.registers.write(1, 0x2000)
        held.registers.write(0, 0xDEADBEEF)

        # Act
        held.step()

        # Assert
        self.assertEqual((held.bus.cycles[1].address, held.bus.cycles[1].nrw), (0x2000, 1))

    def test_a_byte_access_drives_the_width_line_low(self) -> None:
        # Arrange
        held = machine(0xE5C10000)
        held.registers.write(1, 0x2000)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.bus.cycles[1].nbw, 0)

    def test_a_swap_holds_the_lock_line_high_across_both_of_its_accesses(self) -> None:
        # Arrange
        held = machine(SWAP_WORD)
        held.registers.write(2, 0x2000)

        # Act
        held.step()

        # Assert
        self.assertEqual(
            [one.lock for one in held.bus.cycles], [0, 1, 1, 0], quote("lockDuringSwap")
        )

    def test_an_instruction_fetch_drives_the_opcode_line_low(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.bus.cycles[0].nopc, 0, quote("nopcDefinition"))

    def test_a_privileged_mode_drives_the_translate_line_high(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.bus.cycles[0].ntrans, 1, quote("ntransUserMode"))

    def test_and_a_user_mode_drives_it_low(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        held.registers.cpsr = held.registers.cpsr & ~MODE_FIELD | MODES["usr32"].bits

        # Act
        held.step()

        # Assert
        self.assertEqual(held.bus.cycles[0].ntrans, 0, quote("ntransUserMode"))

    def test_a_discarded_prefetch_is_still_a_real_read(self) -> None:
        # Arrange
        held = machine(BRANCH, 0, 0x12345678)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.bus.cycles[0].data, 0x12345678)


if __name__ == "__main__":
    unittest.main(verbosity=2)

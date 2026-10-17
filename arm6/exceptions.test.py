from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import (  # noqa: E402
    VECTORS,
    Cpu,
    Memory,
)
from conformance.printed import quote  # noqa: E402

MOV_R0_R1 = 0xE1A00001
SOFTWARE_INTERRUPT = 0xEF000000
UNDEFINED = 0xE6000010
Z_BIT = 30
I_BIT = 7
F_BIT = 6


def machine(*words: int) -> Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


def with_bit(cpu: Cpu, place: int, level: bool) -> None:
    held = cpu.registers.cpsr
    cpu.registers.cpsr = held | 1 << place if level else held & ~(1 << place)


def bit(cpu: Cpu, place: int) -> bool:
    return bool(cpu.registers.cpsr >> place & 1)


class WhereAnExceptionGoesTest(unittest.TestCase):
    def test_a_software_interrupt_vectors_to_eight(self) -> None:
        # Arrange
        held = machine(SOFTWARE_INTERRUPT)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0x08, quote("exceptionEntry"))

    def test_and_enters_supervisor_mode(self) -> None:
        # Arrange
        held = machine(SOFTWARE_INTERRUPT)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.mode.name, "svc32")

    def test_and_leaves_the_return_address_in_the_link_register(self) -> None:
        # Arrange
        held = machine(SOFTWARE_INTERRUPT)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(14), 4)

    def test_and_banks_the_status_it_came_in_with(self) -> None:
        # Arrange
        held = machine(SOFTWARE_INTERRUPT)
        with_bit(held, Z_BIT, True)
        before = held.registers.cpsr

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.saved(), before)

    def test_an_undefined_instruction_vectors_to_four(self) -> None:
        # Arrange
        held = machine(UNDEFINED)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0x04)

    def test_and_enters_the_undefined_mode(self) -> None:
        # Arrange
        held = machine(UNDEFINED)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.mode.name, "und32")

    def test_every_vector_the_datasheet_lists_is_here(self) -> None:
        # Arrange
        published = VECTORS

        # Act
        held = sorted(published.values())

        # Assert
        self.assertEqual(held, [0x00, 0x04, 0x08, 0x0C, 0x10, 0x18, 0x1C])

    def test_the_address_exception_vector_is_not_among_them(self) -> None:
        # Arrange
        published = VECTORS

        # Act
        held = set(published.values())

        # Assert
        self.assertNotIn(0x14, held)


class TheTwoInterruptLinesTest(unittest.TestCase):
    def test_a_request_on_the_lower_line_is_taken_when_it_is_not_masked(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        with_bit(held, I_BIT, False)

        # Act
        taken = held.irq()

        # Assert
        self.assertTrue(taken)

    def test_and_is_refused_when_it_is(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        with_bit(held, I_BIT, True)

        # Act
        taken = held.irq()

        # Assert
        self.assertFalse(taken)

    def test_a_request_on_the_higher_line_is_masked_by_its_own_bit(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        with_bit(held, F_BIT, True)

        # Act
        taken = held.fiq()

        # Assert
        self.assertFalse(taken)

    def test_a_line_that_is_taken_vectors_on_the_next_instruction(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        with_bit(held, I_BIT, False)
        held.irq()

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0x18)

    def test_the_higher_line_wins_when_both_are_offered(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        with_bit(held, I_BIT, False)
        with_bit(held, F_BIT, False)
        held.irq()
        held.fiq()

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0x1C)

    def test_taking_the_higher_line_masks_both(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        with_bit(held, F_BIT, False)
        held.fiq()

        # Act
        held.step()

        # Assert
        self.assertEqual((bit(held, I_BIT), bit(held, F_BIT)), (True, True))

    def test_a_request_withdrawn_before_the_part_looks_is_not_taken(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        with_bit(held, I_BIT, False)
        held.irq()
        held.irq(level=False)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 4)

    def test_a_masked_request_stays_on_the_line_until_it_is_unmasked(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1, MOV_R0_R1)
        with_bit(held, I_BIT, True)
        held.irq()
        held.step()
        with_bit(held, I_BIT, False)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0x18)


if __name__ == "__main__":
    unittest.main(verbosity=2)

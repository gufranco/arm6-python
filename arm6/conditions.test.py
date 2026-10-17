from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import (  # noqa: E402
    Cpu,
    Memory,
)
from conformance.printed import quote  # noqa: E402

MOV_R0_R1 = 0xE1A00001
Z_BIT = 30
ADD_R0_IMMEDIATE = 0x02800000
ROTATE_TO_SECOND_BYTE = 12 << 8


def machine(*words: int) -> Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


def with_bit(cpu: Cpu, place: int, level: bool) -> None:
    held = cpu.registers.cpsr
    cpu.registers.cpsr = held | 1 << place if level else held & ~(1 << place)


def add_one_bit(code: int, place: int) -> int:
    rotate = ROTATE_TO_SECOND_BYTE if place >= 8 else 0
    return code << 28 | ADD_R0_IMMEDIATE | rotate | 1 << place % 8


class TheConditionFieldDecidesTest(unittest.TestCase):
    def test_an_instruction_whose_condition_holds_executes(self) -> None:
        # Arrange
        held = machine(0x01A00001)
        with_bit(held, Z_BIT, True)
        held.registers.write(1, 0x99)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x99)

    def test_and_one_whose_condition_fails_does_not(self) -> None:
        # Arrange
        held = machine(0x01A00001)
        with_bit(held, Z_BIT, False)
        held.registers.write(1, 0x99)
        held.registers.write(0, 0x11)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x11, quote("conditionNotMet"))

    def test_with_every_flag_clear_each_code_answers_as_the_condition_table_reads(self) -> None:
        # Arrange
        held = machine(*(add_one_bit(code, code) for code in range(16)))

        # Act
        held.run_for(16)

        # Assert
        self.assertEqual(held.registers.read(0), 0b0101_0110_1010_1010)

    def test_with_every_flag_set_each_code_answers_as_the_condition_table_reads(self) -> None:
        # Arrange
        held = machine(*(add_one_bit(code, code) for code in range(16)))
        held.registers.cpsr |= 0xF0000000

        # Act
        held.run_for(16)

        # Assert
        self.assertEqual(held.registers.read(0), 0b0110_0110_0101_0101)

    def test_the_never_code_never_executes(self) -> None:
        # Arrange
        held = machine(0xF1A00001)
        held.registers.write(1, 0x99)
        held.registers.write(0, 0x11)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x11, quote("neverCondition"))

    def test_the_always_code_always_does(self) -> None:
        # Arrange
        held = machine(MOV_R0_R1)
        held.registers.write(1, 0x99)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x99)


if __name__ == "__main__":
    unittest.main(verbosity=2)

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402
from conformance.printed import quote  # noqa: E402

LSL = 0
LSR = 1
ASR = 2
ROR = 3

MOVS_R0_R1 = 0xE1B00001

CARRY = 1 << 29


def by_amount(code: int, operand: int, amount: int, carry: bool) -> arm6.Cpu:
    word = MOVS_R0_R1 | amount << 7 | code << 5
    return prepared(word, operand, 0, carry)


def by_register(code: int, operand: int, amount: int, carry: bool) -> arm6.Cpu:
    word = MOVS_R0_R1 | 2 << 8 | code << 5 | 1 << 4
    return prepared(word, operand, amount, carry)


def prepared(word: int, operand: int, amount: int, carry: bool) -> arm6.Cpu:
    image = word.to_bytes(4, "little")
    cpu = arm6.Cpu("arm60", arm6.Memory(image=image, fill=0), fill=0).reset()
    cpu.registers.write(1, operand)
    cpu.registers.write(2, amount)
    cpu.registers.cpsr = cpu.registers.cpsr | CARRY if carry else cpu.registers.cpsr & ~CARRY
    return cpu


def outcome(cpu: arm6.Cpu) -> tuple[int, bool]:
    return cpu.registers.read(0), bool(cpu.registers.cpsr & CARRY)


class LogicalShiftLeftTest(unittest.TestCase):
    def test_a_shift_moves_the_bits_up_and_fills_with_zeros(self) -> None:
        # Arrange
        cpu = by_amount(LSL, 0x0000_00FF, 8, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_FF00, False))

    def test_the_last_bit_pushed_out_of_the_top_becomes_the_carry(self) -> None:
        # Arrange
        cpu = by_amount(LSL, 0x8000_0001, 1, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0002, True))

    def test_a_shift_of_zero_uses_rm_and_passes_the_old_carry_through(self) -> None:
        # Arrange
        cpu = by_amount(LSL, 0x1234_5678, 0, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x1234_5678, True), quote("lslZero"))

    def test_and_passes_a_cleared_carry_through_just_as_faithfully(self) -> None:
        # Arrange
        cpu = by_amount(LSL, 0x1234_5678, 0, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x1234_5678, False))

    def test_a_shift_of_thirty_one_keeps_only_the_bottom_bit(self) -> None:
        # Arrange
        cpu = by_amount(LSL, 0x0000_0003, 31, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x8000_0000, True))


class LogicalShiftRightTest(unittest.TestCase):
    def test_a_shift_moves_the_bits_down_and_fills_with_zeros(self) -> None:
        # Arrange
        cpu = by_amount(LSR, 0xFF00_0000, 8, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x00FF_0000, False))

    def test_the_last_bit_pushed_out_of_the_bottom_becomes_the_carry(self) -> None:
        # Arrange
        cpu = by_amount(LSR, 0x0000_0003, 1, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0001, True))

    def test_the_encoding_that_would_be_zero_means_thirty_two_instead(self) -> None:
        # Arrange
        cpu = by_amount(LSR, 0x8000_0000, 0, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, True), quote("lsrZero"))

    def test_and_that_encoding_takes_its_carry_from_the_top_bit(self) -> None:
        # Arrange
        cpu = by_amount(LSR, 0x7FFF_FFFF, 0, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, False), quote("lsrZero"))


class ArithmeticShiftRightTest(unittest.TestCase):
    def test_a_shift_fills_the_top_with_the_sign_bit(self) -> None:
        # Arrange
        cpu = by_amount(ASR, 0xFF00_0000, 8, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0xFFFF_0000, False))

    def test_a_positive_value_fills_with_zeros(self) -> None:
        # Arrange
        cpu = by_amount(ASR, 0x7F00_0000, 8, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x007F_0000, False))

    def test_the_encoding_that_would_be_zero_means_thirty_two_instead(self) -> None:
        # Arrange
        cpu = by_amount(ASR, 0x8000_0000, 0, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0xFFFF_FFFF, True))

    def test_and_a_positive_value_under_that_encoding_becomes_all_zeros(self) -> None:
        # Arrange
        cpu = by_amount(ASR, 0x7FFF_FFFF, 0, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, False))


class RotateRightTest(unittest.TestCase):
    def test_the_bits_that_overshoot_come_back_in_at_the_top(self) -> None:
        # Arrange
        cpu = by_amount(ROR, 0x0000_00FF, 4, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0xF000_000F, True))

    def test_the_encoding_that_would_be_zero_is_a_rotate_through_the_carry(self) -> None:
        # Arrange
        cpu = by_amount(ROR, 0x0000_0002, 0, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x8000_0001, False), quote("rrx"))

    def test_and_that_rotate_takes_its_carry_out_from_the_bottom_bit(self) -> None:
        # Arrange
        cpu = by_amount(ROR, 0x0000_0003, 0, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0001, True), quote("rrx"))


class TheSevenCasesForAnAmountOfThirtyTwoOrMoreTest(unittest.TestCase):
    def test_lsl_by_thirty_two_has_result_zero_and_carry_out_bit_zero_of_rm(self) -> None:
        # Arrange
        cpu = by_register(LSL, 0x0000_0001, 32, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, True))

    def test_lsl_by_more_than_thirty_two_has_result_zero_and_carry_out_zero(self) -> None:
        # Arrange
        cpu = by_register(LSL, 0xFFFF_FFFF, 33, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, False))

    def test_lsr_by_thirty_two_has_result_zero_and_carry_out_bit_thirty_one_of_rm(self) -> None:
        # Arrange
        cpu = by_register(LSR, 0x8000_0000, 32, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, True))

    def test_lsr_by_more_than_thirty_two_has_result_zero_and_carry_out_zero(self) -> None:
        # Arrange
        cpu = by_register(LSR, 0xFFFF_FFFF, 40, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, False))

    def test_asr_by_thirty_two_or_more_fills_with_bit_thirty_one_of_rm(self) -> None:
        # Arrange
        cpu = by_register(ASR, 0x8000_0000, 32, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0xFFFF_FFFF, True))

    def test_and_does_the_same_for_an_amount_well_past_thirty_two(self) -> None:
        # Arrange
        cpu = by_register(ASR, 0x7000_0000, 200, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0000, False))

    def test_ror_by_thirty_two_gives_rm_back_with_the_top_bit_as_carry(self) -> None:
        # Arrange
        cpu = by_register(ROR, 0x8000_0001, 32, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x8000_0001, True))

    def test_ror_by_more_than_thirty_two_matches_ror_by_that_amount_less_thirty_two(
        self,
    ) -> None:
        # Arrange
        cpu = by_register(ROR, 0x0000_00FF, 36, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0xF000_000F, True))

    def test_and_a_multiple_of_thirty_two_lands_back_on_the_thirty_two_case(self) -> None:
        # Arrange
        cpu = by_register(ROR, 0x8000_0001, 64, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x8000_0001, True))


class ARegisterSpecifiedAmountReadsOneByteTest(unittest.TestCase):
    def test_an_amount_of_zero_uses_rm_and_the_old_carry(self) -> None:
        # Arrange
        cpu = by_register(LSR, 0x1234_5678, 0, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x1234_5678, True))

    def test_an_amount_between_one_and_thirty_one_matches_the_instruction_form(self) -> None:
        # Arrange
        cpu = by_register(LSR, 0xFF00_0000, 8, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x00FF_0000, False))

    def test_a_rotate_of_zero_from_a_register_is_not_a_rotate_through_the_carry(self) -> None:
        # Arrange
        cpu = by_register(ROR, 0x0000_0002, 0, carry=True)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0002, True))

    def test_only_the_bottom_byte_of_the_register_decides_the_amount(self) -> None:
        # Arrange
        cpu = by_register(LSL, 0x0000_0001, 0xFF00 | 4, carry=False)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(outcome(cpu), (0x0000_0010, False), quote("registerShiftByte"))


class TheFourShiftCodesTest(unittest.TestCase):
    def test_they_are_the_two_bit_field_the_encoding_gives(self) -> None:
        # Arrange
        parts = [by_amount(code, 0x8000_0003, 1, carry=False) for code in range(4)]

        # Act
        spent = [cpu.step() for cpu in parts]

        # Assert
        self.assertEqual(
            ([cpu.registers.read(0) for cpu in parts], spent),
            ([0x0000_0006, 0x4000_0001, 0xC000_0001, 0xC000_0001], [1, 1, 1, 1]),
        )

    def test_a_rotate_and_an_arithmetic_shift_part_ways_on_the_bit_falling_off(self) -> None:
        # Arrange
        parts = [by_amount(code, 0x0000_0003, 1, carry=False) for code in (ASR, ROR)]

        # Act
        spent = [cpu.step() for cpu in parts]

        # Assert
        self.assertEqual(
            ([cpu.registers.read(0) for cpu in parts], spent),
            ([0x0000_0001, 0x8000_0001], [1, 1]),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

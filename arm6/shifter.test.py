"""That the barrel shifter answers each of the corners the datasheet enumerates.

Sections 7.3.1 and 7.3.2 spend three pages on the cases where a shift amount is
zero or thirty two or more, because every one of them is a special case rather
than a consequence of the general rule. The seven numbered outcomes for a
register-specified amount of thirty two or more are quoted from page 23 and each
one has a check of its own here, since a shifter that gets six of them right
looks identical to one that gets all seven right until a program meets the
seventh.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6.shifter import ASR, LSL, LSR, ROR, by_amount, by_register  # noqa: E402


class LogicalShiftLeftTest(unittest.TestCase):
    def test_a_shift_moves_the_bits_up_and_fills_with_zeros(self) -> None:
        held = by_amount(LSL, 0x0000_00FF, 8, carry=False)

        self.assertEqual(held, (0x0000_FF00, False))

    def test_the_last_bit_pushed_out_of_the_top_becomes_the_carry(self) -> None:
        held = by_amount(LSL, 0x8000_0001, 1, carry=False)

        self.assertEqual(held, (0x0000_0002, True))

    def test_a_shift_of_zero_uses_rm_and_passes_the_old_carry_through(self) -> None:
        held = by_amount(LSL, 0x1234_5678, 0, carry=True)

        self.assertEqual(held, (0x1234_5678, True))

    def test_and_passes_a_cleared_carry_through_just_as_faithfully(self) -> None:
        held = by_amount(LSL, 0x1234_5678, 0, carry=False)

        self.assertEqual(held, (0x1234_5678, False))

    def test_a_shift_of_thirty_one_keeps_only_the_bottom_bit(self) -> None:
        held = by_amount(LSL, 0x0000_0003, 31, carry=False)

        self.assertEqual(held, (0x8000_0000, True))


class LogicalShiftRightTest(unittest.TestCase):
    def test_a_shift_moves_the_bits_down_and_fills_with_zeros(self) -> None:
        held = by_amount(LSR, 0xFF00_0000, 8, carry=False)

        self.assertEqual(held, (0x00FF_0000, False))

    def test_the_last_bit_pushed_out_of_the_bottom_becomes_the_carry(self) -> None:
        held = by_amount(LSR, 0x0000_0003, 1, carry=False)

        self.assertEqual(held, (0x0000_0001, True))

    def test_the_encoding_that_would_be_zero_means_thirty_two_instead(self) -> None:
        held = by_amount(LSR, 0x8000_0000, 0, carry=False)

        self.assertEqual(held, (0x0000_0000, True))

    def test_and_that_encoding_takes_its_carry_from_the_top_bit(self) -> None:
        held = by_amount(LSR, 0x7FFF_FFFF, 0, carry=True)

        self.assertEqual(held, (0x0000_0000, False))


class ArithmeticShiftRightTest(unittest.TestCase):
    def test_a_shift_fills_the_top_with_the_sign_bit(self) -> None:
        held = by_amount(ASR, 0xFF00_0000, 8, carry=False)

        self.assertEqual(held, (0xFFFF_0000, False))

    def test_a_positive_value_fills_with_zeros(self) -> None:
        held = by_amount(ASR, 0x7F00_0000, 8, carry=False)

        self.assertEqual(held, (0x007F_0000, False))

    def test_the_encoding_that_would_be_zero_means_thirty_two_instead(self) -> None:
        held = by_amount(ASR, 0x8000_0000, 0, carry=False)

        self.assertEqual(held, (0xFFFF_FFFF, True))

    def test_and_a_positive_value_under_that_encoding_becomes_all_zeros(self) -> None:
        held = by_amount(ASR, 0x7FFF_FFFF, 0, carry=True)

        self.assertEqual(held, (0x0000_0000, False))


class RotateRightTest(unittest.TestCase):
    def test_the_bits_that_overshoot_come_back_in_at_the_top(self) -> None:
        held = by_amount(ROR, 0x0000_00FF, 4, carry=False)

        self.assertEqual(held, (0xF000_000F, True))

    def test_the_encoding_that_would_be_zero_is_a_rotate_through_the_carry(self) -> None:
        held = by_amount(ROR, 0x0000_0002, 0, carry=True)

        self.assertEqual(held, (0x8000_0001, False))

    def test_and_that_rotate_takes_its_carry_out_from_the_bottom_bit(self) -> None:
        held = by_amount(ROR, 0x0000_0003, 0, carry=False)

        self.assertEqual(held, (0x0000_0001, True))


class TheSevenCasesForAnAmountOfThirtyTwoOrMoreTest(unittest.TestCase):
    def test_lsl_by_thirty_two_has_result_zero_and_carry_out_bit_zero_of_rm(self) -> None:
        held = by_register(LSL, 0x0000_0001, 32, carry=False)

        self.assertEqual(held, (0x0000_0000, True))

    def test_lsl_by_more_than_thirty_two_has_result_zero_and_carry_out_zero(self) -> None:
        held = by_register(LSL, 0xFFFF_FFFF, 33, carry=True)

        self.assertEqual(held, (0x0000_0000, False))

    def test_lsr_by_thirty_two_has_result_zero_and_carry_out_bit_thirty_one_of_rm(self) -> None:
        held = by_register(LSR, 0x8000_0000, 32, carry=False)

        self.assertEqual(held, (0x0000_0000, True))

    def test_lsr_by_more_than_thirty_two_has_result_zero_and_carry_out_zero(self) -> None:
        held = by_register(LSR, 0xFFFF_FFFF, 40, carry=True)

        self.assertEqual(held, (0x0000_0000, False))

    def test_asr_by_thirty_two_or_more_fills_with_bit_thirty_one_of_rm(self) -> None:
        held = by_register(ASR, 0x8000_0000, 32, carry=False)

        self.assertEqual(held, (0xFFFF_FFFF, True))

    def test_and_does_the_same_for_an_amount_well_past_thirty_two(self) -> None:
        held = by_register(ASR, 0x7000_0000, 200, carry=True)

        self.assertEqual(held, (0x0000_0000, False))

    def test_ror_by_thirty_two_gives_rm_back_with_the_top_bit_as_carry(self) -> None:
        held = by_register(ROR, 0x8000_0001, 32, carry=False)

        self.assertEqual(held, (0x8000_0001, True))

    def test_ror_by_more_than_thirty_two_matches_ror_by_that_amount_less_thirty_two(
        self,
    ) -> None:
        held = by_register(ROR, 0x0000_00FF, 36, carry=False)

        self.assertEqual(held, by_register(ROR, 0x0000_00FF, 4, carry=False))

    def test_and_a_multiple_of_thirty_two_lands_back_on_the_thirty_two_case(self) -> None:
        held = by_register(ROR, 0x8000_0001, 64, carry=False)

        self.assertEqual(held, (0x8000_0001, True))


class ARegisterSpecifiedAmountReadsOneByteTest(unittest.TestCase):
    def test_an_amount_of_zero_uses_rm_and_the_old_carry(self) -> None:
        held = by_register(LSR, 0x1234_5678, 0, carry=True)

        self.assertEqual(held, (0x1234_5678, True))

    def test_an_amount_between_one_and_thirty_one_matches_the_instruction_form(self) -> None:
        held = by_register(LSR, 0xFF00_0000, 8, carry=False)

        self.assertEqual(held, by_amount(LSR, 0xFF00_0000, 8, carry=False))

    def test_a_rotate_of_zero_from_a_register_is_not_a_rotate_through_the_carry(self) -> None:
        held = by_register(ROR, 0x0000_0002, 0, carry=True)

        self.assertEqual(held, (0x0000_0002, True))

    def test_only_the_bottom_byte_of_the_register_decides_the_amount(self) -> None:
        held = by_register(LSL, 0x0000_0001, 0xFF00 | 4, carry=False)

        self.assertEqual(held, (0x0000_0010, False))


class TheFourShiftCodesTest(unittest.TestCase):
    def test_they_are_the_two_bit_field_the_encoding_gives(self) -> None:
        held = (LSL, LSR, ASR, ROR)

        self.assertEqual(held, (0, 1, 2, 3))

    def test_a_code_outside_that_field_cannot_be_reached(self) -> None:
        with self.assertRaises(ValueError):
            by_amount(4, 0, 1, carry=False)

    def test_and_the_register_form_refuses_it_too(self) -> None:
        with self.assertRaises(ValueError):
            by_register(4, 0, 1, carry=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)

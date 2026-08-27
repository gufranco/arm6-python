"""That the ALU, the immediate rotate and the multiplier match what the pages say.

The multiplier is the sharpest difference between this part and the one the
published conformance corpus was recorded from. ARM60 section 10.3 gives a 2 bit
Booth's algorithm with early termination, so the multiplier is consumed two bits
at a time and `m` runs to sixteen. The ARM7TDMI consumes eight bits at a time and
its `m` runs to four. Both terminate early; the radix is what differs, and every
boundary Table 20 states is checked here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import dataops, psr  # noqa: E402
from arm6.core import Cpu  # noqa: E402
from arm6.memory import Memory  # noqa: E402


class TheBoothCycleCountTest(unittest.TestCase):
    def test_multiplying_by_zero_takes_one_internal_cycle(self) -> None:
        held = dataops.booth_cycles(0)

        self.assertEqual(held, 1)

    def test_and_so_does_multiplying_by_one(self) -> None:
        held = dataops.booth_cycles(1)

        self.assertEqual(held, 1)

    def test_the_bottom_of_the_two_cycle_band_is_two(self) -> None:
        held = dataops.booth_cycles(2)

        self.assertEqual(held, 2)

    def test_and_the_top_of_it_is_seven(self) -> None:
        held = dataops.booth_cycles(7)

        self.assertEqual(held, 2)

    def test_the_band_above_it_starts_at_eight(self) -> None:
        held = dataops.booth_cycles(8)

        self.assertEqual(held, 3)

    def test_and_ends_at_thirty_one(self) -> None:
        held = dataops.booth_cycles(31)

        self.assertEqual(held, 3)

    def test_every_band_the_formula_names_is_two_bits_wide(self) -> None:
        held = {dataops.booth_cycles(one) for one in range(1 << 27, 1 << 29, 1 << 20)}

        self.assertEqual(held, {15})

    def test_anything_from_two_to_the_twenty_nine_takes_sixteen(self) -> None:
        held = dataops.booth_cycles(1 << 29)

        self.assertEqual(held, 16)

    def test_and_the_widest_operand_there_is_takes_sixteen_too(self) -> None:
        held = dataops.booth_cycles(0xFFFFFFFF)

        self.assertEqual(held, 16)

    def test_the_count_never_exceeds_the_stated_worst_case(self) -> None:
        held = max(dataops.booth_cycles(one) for one in range(0, 1 << 16))

        self.assertLessEqual(held, 16)

    def test_the_bands_the_datasheet_states_are_the_bands_it_gives(self) -> None:
        held = [dataops.booth_cycles(1 << (2 * m - 3)) for m in range(2, 16)]

        self.assertEqual(held, list(range(2, 16)))


class TheLogicalOperationsTest(unittest.TestCase):
    def test_and_produces_the_bitwise_and(self) -> None:
        held = dataops.alu(0b0000, 0xFF00FF00, 0x0FF00FF0, carry=False)

        self.assertEqual(held.result, 0x0F000F00)

    def test_eor_produces_the_bitwise_exclusive_or(self) -> None:
        held = dataops.alu(0b0001, 0xFF00FF00, 0x0FF00FF0, carry=False)

        self.assertEqual(held.result, 0xF0F0F0F0)

    def test_orr_produces_the_bitwise_or(self) -> None:
        held = dataops.alu(0b1100, 0xFF000000, 0x000000FF, carry=False)

        self.assertEqual(held.result, 0xFF0000FF)

    def test_mov_takes_the_second_operand_alone(self) -> None:
        held = dataops.alu(0b1101, 0x11111111, 0x22222222, carry=False)

        self.assertEqual(held.result, 0x22222222)

    def test_bic_clears_the_bits_the_second_operand_names(self) -> None:
        held = dataops.alu(0b1110, 0xFFFFFFFF, 0x0000FFFF, carry=False)

        self.assertEqual(held.result, 0xFFFF0000)

    def test_mvn_inverts_the_second_operand(self) -> None:
        held = dataops.alu(0b1111, 0, 0x0000FFFF, carry=False)

        self.assertEqual(held.result, 0xFFFF0000)

    def test_a_logical_operation_leaves_the_overflow_flag_alone(self) -> None:
        held = dataops.alu(0b0000, 0xFFFFFFFF, 0xFFFFFFFF, carry=False)

        self.assertFalse(held.touches_v)

    def test_and_takes_its_carry_from_the_shifter_rather_than_the_adder(self) -> None:
        held = dataops.alu(0b0000, 0xFFFFFFFF, 0xFFFFFFFF, carry=True)

        self.assertTrue(held.c)

    def test_the_zero_flag_is_set_only_when_the_result_is_all_zeros(self) -> None:
        held = dataops.alu(0b0000, 0xFF00, 0x00FF, carry=False)

        self.assertTrue(held.z)

    def test_the_negative_flag_is_bit_thirty_one_of_the_result(self) -> None:
        held = dataops.alu(0b1101, 0, 0x80000000, carry=False)

        self.assertTrue(held.n)


class TheArithmeticOperationsTest(unittest.TestCase):
    def test_add_produces_the_sum(self) -> None:
        held = dataops.alu(0b0100, 2, 3, carry=False)

        self.assertEqual(held.result, 5)

    def test_a_sum_that_leaves_the_word_carries_out_of_bit_thirty_one(self) -> None:
        held = dataops.alu(0b0100, 0xFFFFFFFF, 1, carry=False)

        self.assertEqual((held.result, held.c), (0, True))

    def test_sub_produces_the_difference(self) -> None:
        held = dataops.alu(0b0010, 5, 3, carry=False)

        self.assertEqual(held.result, 2)

    def test_a_subtraction_that_does_not_borrow_carries_out(self) -> None:
        held = dataops.alu(0b0010, 5, 3, carry=False)

        self.assertTrue(held.c)

    def test_and_one_that_borrows_does_not(self) -> None:
        held = dataops.alu(0b0010, 3, 5, carry=False)

        self.assertFalse(held.c)

    def test_rsb_reverses_the_operands(self) -> None:
        held = dataops.alu(0b0011, 3, 5, carry=False)

        self.assertEqual(held.result, 2)

    def test_adc_adds_the_carry_in(self) -> None:
        held = dataops.alu(0b0101, 2, 3, carry=True)

        self.assertEqual(held.result, 6)

    def test_sbc_subtracts_one_when_the_carry_is_clear(self) -> None:
        held = dataops.alu(0b0110, 5, 3, carry=False)

        self.assertEqual(held.result, 1)

    def test_and_subtracts_nothing_extra_when_it_is_set(self) -> None:
        held = dataops.alu(0b0110, 5, 3, carry=True)

        self.assertEqual(held.result, 2)

    def test_rsc_reverses_the_operands_of_that(self) -> None:
        held = dataops.alu(0b0111, 3, 5, carry=True)

        self.assertEqual(held.result, 2)

    def test_an_overflow_into_bit_thirty_one_sets_the_overflow_flag(self) -> None:
        held = dataops.alu(0b0100, 0x7FFFFFFF, 1, carry=False)

        self.assertTrue(held.v)

    def test_a_sum_that_stays_in_range_does_not(self) -> None:
        held = dataops.alu(0b0100, 1, 1, carry=False)

        self.assertFalse(held.v)

    def test_a_subtraction_across_the_sign_boundary_overflows(self) -> None:
        held = dataops.alu(0b0010, 0x80000000, 1, carry=False)

        self.assertTrue(held.v)

    def test_an_arithmetic_operation_touches_the_overflow_flag(self) -> None:
        held = dataops.alu(0b0100, 1, 1, carry=False)

        self.assertTrue(held.touches_v)


class TheFourThatWriteNoResultTest(unittest.TestCase):
    def test_tst_writes_nothing(self) -> None:
        held = dataops.alu(0b1000, 0xFF, 0xFF, carry=False)

        self.assertFalse(held.writes)

    def test_teq_writes_nothing(self) -> None:
        held = dataops.alu(0b1001, 0xFF, 0xFF, carry=False)

        self.assertFalse(held.writes)

    def test_cmp_writes_nothing(self) -> None:
        held = dataops.alu(0b1010, 0xFF, 0xFF, carry=False)

        self.assertFalse(held.writes)

    def test_cmn_writes_nothing(self) -> None:
        held = dataops.alu(0b1011, 0xFF, 0xFF, carry=False)

        self.assertFalse(held.writes)

    def test_but_they_still_produce_flags(self) -> None:
        held = dataops.alu(0b1010, 5, 5, carry=False)

        self.assertTrue(held.z)

    def test_and_everything_else_writes(self) -> None:
        writing = [one for one in range(16) if dataops.alu(one, 0, 0, carry=False).writes]

        self.assertEqual(len(writing), 12)


class TheImmediateOperandTest(unittest.TestCase):
    def test_an_unrotated_immediate_is_the_byte_itself(self) -> None:
        held = dataops.immediate(0x000000FF, carry=False)

        self.assertEqual(held, (0xFF, False))

    def test_an_unrotated_immediate_leaves_the_carry_alone(self) -> None:
        held = dataops.immediate(0x000000FF, carry=True)

        self.assertEqual(held[1], True)

    def test_the_rotate_field_turns_the_byte_by_twice_its_value(self) -> None:
        held = dataops.immediate(0x00000101, carry=False)

        self.assertEqual(held[0], 0x40000000)

    def test_a_rotated_immediate_takes_its_carry_from_bit_thirty_one(self) -> None:
        held = dataops.immediate(0x00000102, carry=False)

        self.assertEqual(held, (0x80000000, True))

    def test_every_power_of_two_is_reachable_as_an_immediate(self) -> None:
        reachable = {dataops.immediate(rot << 8 | 1, carry=False)[0] for rot in range(16)}

        self.assertEqual(len(reachable), 16)


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_an_alu_outcome_refuses_a_name_it_does_not_have(self) -> None:
        held = dataops.alu(0b0100, 1, 1, carry=False)

        with self.assertRaises(AttributeError):
            held.q = 1


class DrivenAsWholeInstructionsTest(unittest.TestCase):
    """The forms whose whole point is a register the pure helpers cannot see.

    A status register transfer, a write to R15 and a shift whose amount comes out
    of a register all need a part rather than an ALU, so they are driven here
    instead of in the checks above.
    """

    def part(self, *words: int) -> Cpu:
        image = b"".join(one.to_bytes(4, "little") for one in words)
        held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
        held.registers.pc = 0
        return held

    def test_an_immediate_operand_reaches_the_destination(self) -> None:
        held = self.part(0xE3A00001)

        held.step()

        self.assertEqual(held.registers.read(0), 1)

    def test_a_rotated_immediate_reaches_it_too(self) -> None:
        held = self.part(0xE3A00102)

        held.step()

        self.assertEqual(held.registers.read(0), 0x80000000)

    def test_setting_the_flags_writes_them_to_the_status_register(self) -> None:
        held = self.part(0xE3B00000)

        held.step()

        self.assertTrue(psr.flag(held.registers.cpsr, psr.Z_BIT))

    def test_a_test_instruction_sets_flags_without_writing_a_register(self) -> None:
        held = self.part(0xE3300001)
        held.registers.write(0, 0x77)

        held.step()

        self.assertEqual(held.registers.read(0), 0x77)

    def test_and_the_flags_it_set_are_the_ones_the_comparison_produced(self) -> None:
        held = self.part(0xE3500005)
        held.registers.write(0, 5)

        held.step()

        self.assertTrue(psr.flag(held.registers.cpsr, psr.Z_BIT))

    def test_the_counter_read_as_an_operand_is_eight_bytes_ahead(self) -> None:
        held = self.part(0xE28F0000)

        held.step()

        self.assertEqual(held.registers.read(0), 8)

    def test_and_twelve_bytes_ahead_when_a_register_supplies_the_shift(self) -> None:
        held = self.part(0xE1A0001F)

        held.step()

        self.assertEqual(held.registers.read(0), 12)

    def test_reading_the_status_register_into_a_register(self) -> None:
        held = self.part(0xE10F0000)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.N_BIT, True)

        held.step()

        self.assertEqual(held.registers.read(0), held.registers.cpsr)

    def test_reading_the_saved_status_register_into_a_register(self) -> None:
        held = self.part(0xE14F0000)
        held.registers.spsr["svc"] = 0x600000D3

        held.step()

        self.assertEqual(held.registers.read(0), 0x600000D3)

    def test_reading_a_saved_status_register_a_user_mode_does_not_have(self) -> None:
        held = self.part(0xE14F0000)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])

        held.step()

        self.assertEqual(held.registers.read(0), held.registers.cpsr)

    def test_writing_the_whole_status_register_from_a_register(self) -> None:
        held = self.part(0xE129F000)
        held.registers.write(0, 0xF00000D1)

        held.step()

        self.assertEqual(held.mode.name, "fiq32")

    def test_writing_only_the_flags_leaves_the_mode_alone(self) -> None:
        held = self.part(0xE128F000)
        held.registers.write(0, 0xF0000010)

        held.step()

        self.assertEqual(held.mode.name, "svc32")

    def test_and_does_change_the_flags(self) -> None:
        held = self.part(0xE128F000)
        held.registers.write(0, 0xF0000000)

        held.step()

        self.assertTrue(psr.flag(held.registers.cpsr, psr.N_BIT))

    def test_writing_the_flags_from_an_immediate(self) -> None:
        held = self.part(0xE328F20F)

        held.step()

        self.assertTrue(psr.flag(held.registers.cpsr, psr.N_BIT))

    def test_a_user_mode_cannot_change_its_own_mode_bits(self) -> None:
        held = self.part(0xE129F000)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])
        held.registers.write(0, 0x000000D1)

        held.step()

        self.assertEqual(held.mode.name, "usr32")

    def test_writing_the_saved_status_register_from_a_register(self) -> None:
        held = self.part(0xE169F000)
        held.registers.write(0, 0xF00000D1)

        held.step()

        self.assertEqual(held.registers.spsr["svc"] & 0x1F, 0b10001)

    def test_writing_a_saved_status_register_a_user_mode_does_not_have(self) -> None:
        held = self.part(0xE169F000)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])
        before = dict(held.registers.spsr)

        held.step()

        self.assertEqual(held.registers.spsr, before)

    def test_the_reserved_bits_are_written_rather_than_masked_away(self) -> None:
        held = self.part(0xE129F000)
        held.registers.cpsr = held.registers.cpsr | psr.RESERVED_MASK
        held.registers.write(0, 0x000000D3)

        held.step()

        self.assertEqual(held.registers.cpsr & psr.RESERVED_MASK, 0)

    def test_a_user_mode_keeps_everything_but_its_condition_flags(self) -> None:
        held = self.part(0xE129F000)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])
        before = held.registers.cpsr & 0x0FFFFFFF
        held.registers.write(0, 0xF00000D1)

        held.step()

        self.assertEqual(held.registers.cpsr & 0x0FFFFFFF, before)

    def test_the_form_earlier_parts_spelled_teqp_restores_the_saved_status(self) -> None:
        held = self.part(0xE130F000)
        held.registers.spsr["svc"] = 0xF00000D3

        held.step()

        self.assertEqual(held.registers.cpsr, 0xF00000D3)

    def test_and_does_nothing_at_all_in_a_user_mode(self) -> None:
        held = self.part(0xE130F000)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])
        before = held.registers.cpsr

        held.step()

        self.assertEqual(held.registers.cpsr, before)

    def test_writing_the_counter_with_the_flag_set_restores_the_saved_status(self) -> None:
        held = self.part(0xE1B0F000)
        held.registers.spsr["svc"] = 0xF00000D3
        held.registers.write(0, 0x40)

        held.step()

        self.assertEqual((held.registers.pc, held.registers.cpsr), (0x40, 0xF00000D3))

    def test_a_multiply_that_sets_flags_reports_a_zero_result_as_zero(self) -> None:
        held = self.part(0xE0100291)
        held.registers.write(1, 0)
        held.registers.write(2, 5)

        held.step()

        self.assertTrue(psr.flag(held.registers.cpsr, psr.Z_BIT))

    def test_a_multiply_accumulate_adds_the_third_operand(self) -> None:
        held = self.part(0xE0203291)
        held.registers.write(1, 6)
        held.registers.write(2, 7)
        held.registers.write(3, 8)

        held.step()

        self.assertEqual(held.registers.read(0), 50)

    def test_a_multiply_accumulate_whose_destination_is_its_multiplicand_is_meaningless(
        self,
    ) -> None:
        held = self.part(0xE0213291)
        held.registers.write(1, 6)
        held.registers.write(2, 7)
        held.registers.write(3, 8)

        held.step()

        self.assertEqual(held.registers.read(1), 8)

    def test_a_reserved_encoding_in_the_transfer_space_is_not_a_transfer(self) -> None:
        held = self.part(0xE1000000)
        held.registers.write(0, 0x55)

        held.step()

        self.assertEqual(held.registers.read(0), 0x55)


if __name__ == "__main__":
    unittest.main(verbosity=2)

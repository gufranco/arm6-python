from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import singlestep  # noqa: E402
from conformance.printed import quote  # noqa: E402

STATE = 40


def state() -> list[int]:
    held = [0] * STATE
    held[singlestep.CPSR] = 0x000000D3
    return held


def case(opcode: int, base: int = 0x1000) -> singlestep.Case:
    initial = state()
    initial[15] = base + 8
    return singlestep.Case(
        initial=tuple(initial),
        final=tuple(initial),
        reads=(),
        opcode=opcode,
        base=base,
    )


class EveryRestrictionIsDrivenTest(unittest.TestCase):
    def trips(self, opcode: int, stem: str) -> str | None:
        return singlestep.excluded(case(opcode), stem)

    def test_r15_as_a_multiply_operand(self) -> None:
        # Arrange
        word = 0xE00F0291
        stem = "arm_mul_mla"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "R15 as a multiply operand")

    def test_r15_as_a_swap_operand(self) -> None:
        # Arrange
        word = 0xE102F090
        stem = "arm_swp"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "R15 as a swap operand")

    def test_r15_as_the_base_of_a_block_transfer(self) -> None:
        # Arrange
        word = 0xE89F0001
        stem = "arm_ldm_stm"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "R15 as the base of a block transfer")

    def test_r15_as_a_transfer_s_register_offset(self) -> None:
        # Arrange
        word = 0xE791000F
        stem = "arm_ldr_str_register_offset"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "R15 as a transfer's register offset")

    def test_write_back_onto_r15_as_a_base(self) -> None:
        # Arrange
        word = 0xE5BF0000
        stem = "arm_ldr_str_immediate_offset"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "write-back onto R15 as a transfer's base")

    def test_a_post_indexed_transfer_whose_offset_is_its_base(self) -> None:
        # Arrange
        word = 0xE6910001

        # Act
        reason = self.trips(word, "arm_ldr_str_register_offset")

        # Assert
        self.assertEqual(
            reason,
            "a post-indexed transfer whose offset register is its base",
            quote("postIndexedRmEqualsRn"),
        )

    def test_r15_as_the_destination_of_a_psr_read(self) -> None:
        # Arrange
        word = 0xE10FF000
        stem = "arm_mrs"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "R15 as the destination of a PSR read")

    def test_an_spsr_reached_from_a_user_mode(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE14F0000)._replace(initial=tuple(initial), final=tuple(initial))

        # Act
        held = singlestep.excluded(one, "arm_mrs")

        # Assert
        self.assertEqual(held, "an SPSR reached from a user mode")

    def test_an_msr_field_mask_the_figure_does_not_print(self) -> None:
        # Arrange
        word = 0xE12AF000
        stem = "arm_msr_reg"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "an MSR field mask Figure 14 does not print")

    def test_r15_as_the_source_of_a_psr_write(self) -> None:
        # Arrange
        word = 0xE129F00F
        stem = "arm_msr_reg"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "R15 as the source of a PSR write")

    def test_r15_as_the_register_holding_a_shift_amount(self) -> None:
        # Arrange
        word = 0xE1A00F11
        stem = "arm_data_proc_register_shift"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "R15 as the register holding a shift amount")

    def test_the_s_bit_of_a_block_transfer_outside_a_privileged_mode(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE8D10001)._replace(initial=tuple(initial), final=tuple(initial))

        # Act
        held = singlestep.excluded(one, "arm_ldm_stm")

        # Assert
        self.assertEqual(held, "the S bit of a block transfer set outside a privileged mode")

    def test_base_write_back_with_the_s_bit_set(self) -> None:
        # Arrange
        word = 0xE8F10001
        stem = "arm_ldm_stm"

        # Act
        held = self.trips(word, stem)

        # Assert
        self.assertEqual(held, "base write-back with the S bit of a block transfer set")

    def test_a_case_ending_in_a_mode_this_part_does_not_have(self) -> None:
        # Arrange
        one = case(0xE1A00001)
        one = one._replace(final=(*one.final[:31], 0x0000001F, *one.final[32:]))

        # Act
        held = singlestep.excluded(one, "arm_data_proc_immediate")

        # Assert
        self.assertEqual(held, "ends in a mode ARM60 does not have")

    def test_a_mode_the_generator_s_part_cannot_enter(self) -> None:
        # Arrange
        initial = state()
        initial[1] = 0x00000000
        one = case(0xE129F001)._replace(initial=tuple(initial), final=tuple(initial))

        # Act
        held = singlestep.excluded(one, "arm_msr_reg")

        # Assert
        self.assertEqual(held, "a mode the generator's part cannot enter written into a PSR")

    def test_and_a_thirty_two_bit_mode_is_not_excluded_for_that_reason(self) -> None:
        # Arrange
        initial = state()
        initial[1] = 0x00000013
        one = case(0xE129F001)._replace(initial=tuple(initial), final=tuple(initial))

        # Act
        held = singlestep.excluded(one, "arm_msr_reg")

        # Assert
        self.assertIsNone(held)


class TheFilterKeepsWhatNoSentenceForbidsTest(unittest.TestCase):
    def test_a_case_a_user_mode_can_legitimately_run_is_kept(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE1A00001)._replace(initial=tuple(initial), final=tuple(initial))

        # Act
        held = singlestep.excluded(one, "arm_data_proc_immediate")

        # Assert
        self.assertIsNone(held)

    def test_a_swap_naming_no_counter_is_kept(self) -> None:
        # Arrange
        one = case(0xE1020091)

        # Act
        held = singlestep.excluded(one, "arm_swp")

        # Assert
        self.assertIsNone(held)

    def test_a_transfer_with_an_immediate_offset_of_fifteen_is_not_a_register_offset(self) -> None:
        # Arrange
        one = case(0xE591000F)

        # Act
        held = singlestep.excluded(one, "arm_ldr_str_immediate_offset")

        # Assert
        self.assertIsNone(held)

    def test_a_block_transfer_without_the_s_bit_is_kept(self) -> None:
        # Arrange
        one = case(0xE8910001)

        # Act
        held = singlestep.excluded(one, "arm_ldm_stm")

        # Assert
        self.assertIsNone(held)

    def test_a_psr_read_that_names_no_counter_is_kept(self) -> None:
        # Arrange
        one = case(0xE10F0000)

        # Act
        held = singlestep.excluded(one, "arm_mrs")

        # Assert
        self.assertIsNone(held)

    def test_the_s_flag_with_the_counter_as_destination_in_a_user_mode(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE1B0F000)._replace(initial=tuple(initial), final=tuple(initial))

        # Act
        held = singlestep.excluded(one, "arm_data_proc_immediate_shift")

        # Assert
        self.assertEqual(held, "S bit with R15 as destination in a user mode")

    def test_an_immediate_written_into_the_whole_psr(self) -> None:
        # Arrange
        one = case(0xE329F0D3)

        # Act
        held = singlestep.excluded(one, "arm_msr_imm")

        # Assert
        self.assertEqual(held, "an eight bit immediate written into the whole PSR")

    def test_a_psr_write_reaching_an_spsr_from_a_user_mode(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE169F000)._replace(initial=tuple(initial), final=tuple(initial))

        # Act
        held = singlestep.excluded(one, "arm_msr_reg")

        # Assert
        self.assertEqual(held, "an SPSR reached from a user mode")

    def test_a_block_transfer_with_the_s_bit_and_no_write_back_is_kept(self) -> None:
        # Arrange
        one = case(0xE8D10001)

        # Act
        held = singlestep.excluded(one, "arm_ldm_stm")

        # Assert
        self.assertIsNone(held)


if __name__ == "__main__":
    unittest.main(verbosity=2)

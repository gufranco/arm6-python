"""That a word read rather than run comes back as the instruction it is.

The package could already say which of Figure 28's eleven rows a word belongs to,
and that is all it could say. Walking an image with it meant writing a second
decoder outside the package, which is how a member ends up with two decoders that
disagree. These checks hold the one inside it to the same shape every other
member of this family publishes: an instruction that knows where it was found,
what it is, and how a reader would write it.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import decode, disassembly, errors  # noqa: E402


def image(*words: int) -> bytes:
    return b"".join(word.to_bytes(4, "little") for word in words)


class Fixture(unittest.TestCase):
    def only(self, word: int, address: int = 0) -> disassembly.Instruction:
        return disassembly.decode(image(word), 0, address)


class OneWordTest(Fixture):
    def test_a_word_knows_where_it_was_found(self) -> None:
        found = disassembly.decode(image(0xEA000000, 0xEA000000), 4, 0x1000)

        self.assertEqual((found.address, found.offset, found.size), (0x1000, 4, 4))

    def test_a_word_carries_the_condition_the_datasheet_names(self) -> None:
        found = self.only(0x1A000000)

        self.assertEqual(found.condition, "NE")

    def test_a_word_carries_the_row_of_figure_28_it_belongs_to(self) -> None:
        found = self.only(0xEA000000)

        self.assertEqual(found.kind, decode.BRANCH)

    def test_a_word_shorter_than_an_instruction_is_refused(self) -> None:
        with self.assertRaises(errors.Truncated):
            disassembly.decode(b"\x00\x00\x00")

    def test_an_offset_outside_the_image_is_refused(self) -> None:
        with self.assertRaises(errors.Truncated):
            disassembly.decode(image(0xEA000000), 8)


class BranchTest(Fixture):
    def test_a_branch_forwards_resolves_its_target(self) -> None:
        found = self.only(0xEA00002A, 0x000000)

        self.assertEqual((found.mnemonic, found.operand, found.text), ("b", 0x0000B0, "b 0x0000B0"))

    def test_a_branch_backwards_resolves_its_target(self) -> None:
        found = self.only(0xEAFFFFFE, 0x001000)

        self.assertEqual(found.operand, 0x001000)

    def test_a_branch_with_link_says_so(self) -> None:
        found = self.only(0xEB00003F, 0x0001AC)

        self.assertEqual((found.mnemonic, found.text), ("bl", "bl 0x0002B0"))

    def test_a_conditional_branch_carries_its_condition_into_the_text(self) -> None:
        found = self.only(0x0A000010, 0x0001A8)

        self.assertEqual(found.text, "beq 0x0001F0")


class DataProcessingTest(Fixture):
    def test_a_move_of_an_immediate_reads_as_one(self) -> None:
        found = self.only(0xE3A09181)

        self.assertEqual(
            (found.mnemonic, found.operand, found.text), ("mov", 0x40000020, "mov R9, #0x40000020")
        )

    def test_a_move_of_a_register_reads_as_one(self) -> None:
        found = self.only(0xE1A0F00E)

        self.assertEqual(found.text, "mov PC, LR")

    def test_a_three_operand_operation_names_both_sources(self) -> None:
        found = self.only(0xE2100001)

        self.assertEqual(found.text, "ands R0, R0, #0x1")

    def test_a_comparison_names_no_destination(self) -> None:
        found = self.only(0xE3100020)

        self.assertEqual((found.mnemonic, found.text), ("tst", "tst R0, #0x20"))

    def test_a_shifted_register_operand_names_its_shift(self) -> None:
        found = self.only(0xE1A00240)

        self.assertEqual(found.text, "mov R0, R0, asr #4")

    def test_a_register_controlled_shift_names_the_register(self) -> None:
        found = self.only(0xE1A00310)

        self.assertEqual(found.text, "mov R0, R0, lsl R3")

    def test_a_rotate_of_zero_is_left_out_of_the_text(self) -> None:
        found = self.only(0xE1A00000)

        self.assertEqual(found.text, "mov R0, R0")

    def test_a_shift_of_zero_that_means_thirty_two_says_thirty_two(self) -> None:
        """The datasheet gives a zero amount on LSR and ASR the meaning 32.

        Only LSL keeps zero meaning zero, which is why it is the one written
        without a shift at all.
        """
        found = self.only(0xE1A00020)

        self.assertEqual(found.text, "mov R0, R0, lsr #32")

    def test_a_rotate_right_extended_is_written_as_the_datasheet_does(self) -> None:
        found = self.only(0xE1A00060)

        self.assertEqual(found.text, "mov R0, R0, rrx")

    def test_reading_the_status_register_is_not_a_comparison(self) -> None:
        found = self.only(0xE10F0000)

        self.assertEqual((found.mnemonic, found.text), ("mrs", "mrs R0, cpsr"))

    def test_reading_the_saved_status_register_names_it(self) -> None:
        found = self.only(0xE14F0000)

        self.assertEqual(found.text, "mrs R0, spsr")

    def test_writing_the_whole_status_register_names_it(self) -> None:
        found = self.only(0xE129F000)

        self.assertEqual((found.mnemonic, found.text), ("msr", "msr cpsr, R0"))

    def test_writing_only_the_flags_says_so(self) -> None:
        found = self.only(0xE128F000)

        self.assertEqual(found.text, "msr cpsr_flg, R0")

    def test_writing_the_flags_from_an_immediate_reads_as_one(self) -> None:
        found = self.only(0xE328F00F)

        self.assertEqual(found.text, "msr cpsr_flg, #0xF")


class MultiplyTest(Fixture):
    def test_a_multiply_names_its_three_registers(self) -> None:
        found = self.only(0xE0000291)

        self.assertEqual((found.mnemonic, found.text), ("mul", "mul R0, R1, R2"))

    def test_a_multiply_that_accumulates_names_the_fourth(self) -> None:
        found = self.only(0xE0234192)

        self.assertEqual((found.mnemonic, found.text), ("mla", "mla R3, R2, R1, R4"))

    def test_a_multiply_that_sets_the_flags_says_so(self) -> None:
        found = self.only(0xE0100291)

        self.assertEqual(found.text, "muls R0, R1, R2")


class SwapTest(Fixture):
    def test_a_word_swap_names_its_registers(self) -> None:
        found = self.only(0xE1021093)

        self.assertEqual((found.mnemonic, found.text), ("swp", "swp R1, R3, [R2]"))

    def test_a_byte_swap_says_so(self) -> None:
        found = self.only(0xE1421093)

        self.assertEqual(found.mnemonic, "swpb")


class SingleDataTransferTest(Fixture):
    def test_a_load_with_no_offset_leaves_it_out(self) -> None:
        found = self.only(0xE5100000)

        self.assertEqual((found.mnemonic, found.operand, found.text), ("ldr", 0, "ldr R0, [R0]"))

    def test_a_store_with_an_immediate_offset_names_it(self) -> None:
        found = self.only(0xE5898004)

        self.assertEqual(
            (found.mnemonic, found.operand, found.text), ("str", 4, "str R8, [R9, #0x4]")
        )

    def test_a_negative_immediate_offset_is_signed(self) -> None:
        found = self.only(0xE5198004)

        self.assertEqual((found.operand, found.text), (-4, "ldr R8, [R9, #-0x4]"))

    def test_a_byte_load_says_so(self) -> None:
        found = self.only(0xE5DB0020)

        self.assertEqual((found.mnemonic, found.text), ("ldrb", "ldrb R0, [R11, #0x20]"))

    def test_a_load_relative_to_the_program_counter_resolves_the_literal(self) -> None:
        found = self.only(0xE59F0788, 0x00011C)

        self.assertEqual((found.operand, found.text), (0x0008AC, "ldr R0, [PC, #0x788]"))

    def test_a_register_offset_names_the_register(self) -> None:
        found = self.only(0xE7910002)

        self.assertEqual((found.operand, found.text), (None, "ldr R0, [R1, R2]"))

    def test_a_shifted_register_offset_names_the_shift(self) -> None:
        found = self.only(0xE7910102)

        self.assertEqual(found.text, "ldr R0, [R1, R2, lsl #2]")

    def test_a_post_indexed_transfer_writes_the_offset_outside_the_brackets(self) -> None:
        found = self.only(0xE4910004)

        self.assertEqual(found.text, "ldr R0, [R1], #0x4")

    def test_a_pre_indexed_transfer_that_writes_back_says_so(self) -> None:
        found = self.only(0xE5B10004)

        self.assertEqual(found.text, "ldr R0, [R1, #0x4]!")

    def test_a_post_indexed_transfer_that_forces_user_mode_says_so(self) -> None:
        found = self.only(0xE6B10002)

        self.assertEqual(found.mnemonic, "ldrt")

    def test_a_byte_transfer_that_forces_user_mode_says_both(self) -> None:
        found = self.only(0xE6F10002)

        self.assertEqual(found.mnemonic, "ldrbt")


class BlockDataTransferTest(Fixture):
    def test_a_push_reads_as_the_datasheet_writes_it(self) -> None:
        found = self.only(0xE92D4300)

        self.assertEqual((found.mnemonic, found.text), ("stmdb", "stmdb SP!, {R8, R9, LR}"))

    def test_a_pop_reads_as_the_datasheet_writes_it(self) -> None:
        found = self.only(0xE8BD8300)

        self.assertEqual((found.mnemonic, found.text), ("ldmia", "ldmia SP!, {R8, R9, PC}"))

    def test_the_two_remaining_addressing_modes_are_named(self) -> None:
        after = self.only(0xE8100001)
        before = self.only(0xE9900001)

        self.assertEqual((after.mnemonic, before.mnemonic), ("ldmda", "ldmib"))

    def test_a_transfer_of_the_user_bank_says_so(self) -> None:
        found = self.only(0xE8500001)

        self.assertEqual(found.text, "ldmda R0, {R0}^")

    def test_a_transfer_with_no_registers_says_so_rather_than_showing_nothing(self) -> None:
        found = self.only(0xE8100000)

        self.assertEqual(found.text, "ldmda R0, {}")


class SoftwareInterruptTest(Fixture):
    def test_a_software_interrupt_carries_its_comment_field(self) -> None:
        found = self.only(0xEF123456)

        self.assertEqual(
            (found.mnemonic, found.operand, found.text), ("swi", 0x123456, "swi 0x123456")
        )


class CoprocessorTest(Fixture):
    def test_a_coprocessor_load_names_the_coprocessor(self) -> None:
        found = self.only(0xED910102)

        self.assertEqual(
            (found.mnemonic, found.operand, found.text), ("ldc", 8, "ldc p1, c0, [R1, #0x8]")
        )

    def test_a_post_indexed_coprocessor_transfer_writes_the_offset_outside(self) -> None:
        found = self.only(0xEC910102)

        self.assertEqual(found.text, "ldc p1, c0, [R1], #0x8")

    def test_a_coprocessor_store_says_so(self) -> None:
        found = self.only(0xED810102)

        self.assertEqual(found.mnemonic, "stc")

    def test_a_coprocessor_operation_names_its_registers(self) -> None:
        found = self.only(0xEE123104)

        self.assertEqual((found.mnemonic, found.text), ("cdp", "cdp p1, 1, c3, c2, c4, 0"))

    def test_a_move_to_a_coprocessor_reads_as_one(self) -> None:
        found = self.only(0xEE213114)

        self.assertEqual((found.mnemonic, found.text), ("mcr", "mcr p1, 1, R3, c1, c4, 0"))

    def test_a_move_from_a_coprocessor_reads_as_one(self) -> None:
        found = self.only(0xEE313114)

        self.assertEqual(found.mnemonic, "mrc")


class OutsideTheFigureTest(Fixture):
    def test_the_row_the_figure_marks_undefined_reads_as_itself(self) -> None:
        found = self.only(0xE6000010)

        self.assertEqual(
            (found.kind, found.mnemonic, found.text),
            (decode.UNDEFINED, "undefined", "undefined 0xE6000010"),
        )

    def test_an_encoding_outside_the_figure_is_shown_rather_than_refused(self) -> None:
        """A walk over an image crosses data, and data is not an instruction.

        Refusing here would stop the walk at the first constant. The word is
        handed back under the name the package already uses for it.
        """
        found = self.only(0x000000D0)

        self.assertEqual((found.kind, found.mnemonic), (decode.UNSPECIFIED, "unspecified"))


class ConditionSpellingTest(Fixture):
    """Where the condition goes, which assembly does not always put at the end."""

    def test_a_condition_follows_the_operation_rather_than_the_suffix(self) -> None:
        found = self.only(0x15DB0020)

        self.assertEqual((found.mnemonic, found.text), ("ldrb", "ldrneb R0, [R11, #0x20]"))

    def test_a_transfer_with_no_suffix_takes_the_condition_at_the_end(self) -> None:
        found = self.only(0x15910000)

        self.assertEqual(found.text, "ldrne R0, [R1]")

    def test_a_flag_setting_suffix_stays_where_it_is(self) -> None:
        found = self.only(0x12100001)

        self.assertEqual(found.text, "andnes R0, R0, #0x1")


class WalkTest(unittest.TestCase):
    def test_a_walk_returns_every_instruction_in_order(self) -> None:
        found = disassembly.disassemble(image(0xE3A08000, 0xE3A09181, 0xE5098000), address=0x100)

        self.assertEqual([one.address for one in found], [0x100, 0x104, 0x108])

    def test_a_walk_stops_at_the_count_it_was_given(self) -> None:
        found = disassembly.disassemble(image(0xE3A08000, 0xE3A09181), count=1)

        self.assertEqual(len(found), 1)

    def test_a_walk_stops_when_the_image_runs_out(self) -> None:
        found = disassembly.disassemble(image(0xE3A08000) + b"\x00\x00")

        self.assertEqual(len(found), 1)

    def test_a_walk_can_stop_where_a_routine_returns(self) -> None:
        found = disassembly.disassemble(
            image(0xE3A08000, 0xE1A0F00E, 0xE3A09181), stop_at_return=True
        )

        self.assertEqual(len(found), 2)

    def test_a_walk_that_is_not_asked_to_stop_carries_on_past_a_return(self) -> None:
        found = disassembly.disassemble(image(0xE1A0F00E, 0xE3A09181))

        self.assertEqual(len(found), 2)


class ReturnTest(Fixture):
    def test_moving_the_link_register_into_the_counter_is_a_return(self) -> None:
        self.assertTrue(disassembly.returns(self.only(0xE1A0F00E)))

    def test_loading_the_counter_off_the_stack_is_a_return(self) -> None:
        self.assertTrue(disassembly.returns(self.only(0xE8BD8300)))

    def test_a_load_that_leaves_the_counter_alone_is_not_a_return(self) -> None:
        self.assertFalse(disassembly.returns(self.only(0xE8BD0300)))

    def test_a_store_that_names_the_counter_is_not_a_return(self) -> None:
        self.assertFalse(disassembly.returns(self.only(0xE92D8300)))

    def test_moving_something_else_into_the_counter_is_not_a_return(self) -> None:
        self.assertFalse(disassembly.returns(self.only(0xE1A0F000)))

    def test_moving_the_link_register_somewhere_else_is_not_a_return(self) -> None:
        self.assertFalse(disassembly.returns(self.only(0xE1A0000E)))

    def test_an_instruction_of_another_kind_is_not_a_return(self) -> None:
        self.assertFalse(disassembly.returns(self.only(0xEA000000)))


class AgainstTheDatasheetTest(unittest.TestCase):
    """Words taken from the datasheet's own examples, read back as it writes them."""

    def test_every_condition_the_datasheet_numbers_renders(self) -> None:
        rendered = [
            disassembly.decode(image((code << 28) | 0x0A000000)).text.split()[0]
            for code in range(16)
        ]

        self.assertEqual(rendered[:3] + rendered[14:], ["beq", "bne", "bcs", "b", "bnv"])

    def test_every_row_of_the_figure_has_a_mnemonic(self) -> None:
        words = (
            0xE0000291,
            0xE1021093,
            0xE5100000,
            0xE6000010,
            0xE8100001,
            0xEA000000,
            0xED910102,
            0xEE123104,
            0xEE313114,
            0xEF123456,
            0xE1A00000,
        )

        found = {disassembly.decode(image(word)).kind for word in words}

        self.assertEqual(found, set(decode.KINDS))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402

BRANCH = 0xEA000000

MOVE = 0xE3A09181

FIGURE_28_ROWS = {
    "data processing",
    "multiply",
    "single data swap",
    "single data transfer",
    "undefined",
    "block data transfer",
    "branch",
    "coprocessor data transfer",
    "coprocessor data operation",
    "coprocessor register transfer",
    "software interrupt",
}


def image(*words: int) -> bytes:
    return b"".join(word.to_bytes(4, "little") for word in words)


def spelled(found: list[Any]) -> list[tuple[str, str]]:
    return [(one.mnemonic, one.text) for one in found]


class OneWordTest(unittest.TestCase):
    def test_a_word_knows_where_it_was_found_and_what_it_is(self) -> None:
        # Arrange
        data = image(BRANCH, 0x1A000000)

        # Act
        found = arm6.disassemble(data, offset=4, address=0x1000)

        # Assert
        self.assertEqual(
            [(one.address, one.offset, one.size, one.condition, one.kind) for one in found],
            [(0x1000, 4, 4, "NE", "branch")],
        )

    def test_a_word_shorter_than_an_instruction_ends_the_listing(self) -> None:
        # Arrange
        data = b"\x00\x00\x00"

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(found, [])

    def test_an_offset_outside_the_image_ends_the_listing(self) -> None:
        # Arrange
        data = image(BRANCH)

        # Act
        found = arm6.disassemble(data, offset=8)

        # Assert
        self.assertEqual(found, [])


class BranchTest(unittest.TestCase):
    def test_a_branch_forwards_resolves_its_target(self) -> None:
        # Arrange
        data = image(0xEA00002A)

        # Act
        found = arm6.disassemble(data, address=0)

        # Assert
        self.assertEqual(
            [(one.mnemonic, one.operand, one.text) for one in found], [("b", 0xB0, "b 0x0000B0")]
        )

    def test_a_branch_backwards_resolves_its_target(self) -> None:
        # Arrange
        data = image(0xEAFFFFFE)

        # Act
        found = arm6.disassemble(data, address=0x1000)

        # Assert
        self.assertEqual([one.operand for one in found], [0x1000])

    def test_a_branch_with_link_says_so(self) -> None:
        # Arrange
        data = image(0xEB00003F)

        # Act
        found = arm6.disassemble(data, address=0x1AC)

        # Assert
        self.assertEqual(spelled(found), [("bl", "bl 0x0002B0")])

    def test_a_conditional_branch_carries_its_condition_into_the_text(self) -> None:
        # Arrange
        data = image(0x0A000010)

        # Act
        found = arm6.disassemble(data, address=0x1A8)

        # Assert
        self.assertEqual(spelled(found), [("b", "beq 0x0001F0")])


class DataProcessingTest(unittest.TestCase):
    def test_each_operand_shape_names_its_registers_and_its_number(self) -> None:
        # Arrange
        data = image(MOVE, 0xE1A0F00E, 0xE2100001, 0xE3100020)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [(one.mnemonic, one.operand, one.text) for one in found],
            [
                ("mov", 0x40000020, "mov R9, #0x40000020"),
                ("mov", None, "mov PC, LR"),
                ("ands", 1, "ands R0, R0, #0x1"),
                ("tst", 0x20, "tst R0, #0x20"),
            ],
        )

    def test_a_shifted_register_operand_names_its_shift_and_each_zero_amount(self) -> None:
        # Arrange
        data = image(0xE1A00240, 0xE1A00310, 0xE1A00000, 0xE1A00020, 0xE1A00060)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [one.text for one in found],
            [
                "mov R0, R0, asr #4",
                "mov R0, R0, lsl R3",
                "mov R0, R0",
                "mov R0, R0, lsr #32",
                "mov R0, R0, rrx",
            ],
        )

    def test_a_status_register_transfer_is_not_a_comparison(self) -> None:
        # Arrange
        data = image(0xE10F0000, 0xE14F0000, 0xE129F000, 0xE128F000, 0xE328F00F)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found),
            [
                ("mrs", "mrs R0, cpsr"),
                ("mrs", "mrs R0, spsr"),
                ("msr", "msr cpsr, R0"),
                ("msr", "msr cpsr_flg, R0"),
                ("msr", "msr cpsr_flg, #0xF"),
            ],
        )


class MultiplyAndSwapTest(unittest.TestCase):
    def test_a_multiply_names_its_registers_and_whether_it_sets_the_flags(self) -> None:
        # Arrange
        data = image(0xE0000291, 0xE0234192, 0xE0100291)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found),
            [
                ("mul", "mul R0, R1, R2"),
                ("mla", "mla R3, R2, R1, R4"),
                ("muls", "muls R0, R1, R2"),
            ],
        )

    def test_a_swap_names_its_registers_and_its_width(self) -> None:
        # Arrange
        data = image(0xE1021093, 0xE1421093)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found), [("swp", "swp R1, R3, [R2]"), ("swpb", "swpb R1, R3, [R2]")]
        )


class SingleDataTransferTest(unittest.TestCase):
    def test_an_immediate_offset_is_carried_as_the_operand(self) -> None:
        # Arrange
        data = image(0xE5100000, 0xE5898004, 0xE5198004, 0xE5DB0020)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [(one.mnemonic, one.operand, one.text) for one in found],
            [
                ("ldr", 0, "ldr R0, [R0]"),
                ("str", 4, "str R8, [R9, #0x4]"),
                ("ldr", -4, "ldr R8, [R9, #-0x4]"),
                ("ldrb", 0x20, "ldrb R0, [R11, #0x20]"),
            ],
        )

    def test_a_load_relative_to_the_program_counter_resolves_the_literal(self) -> None:
        # Arrange
        data = image(0xE59F0788)

        # Act
        found = arm6.disassemble(data, address=0x11C)

        # Assert
        self.assertEqual(
            [(one.operand, one.text) for one in found], [(0x8AC, "ldr R0, [PC, #0x788]")]
        )

    def test_a_register_offset_names_the_register_and_carries_no_number(self) -> None:
        # Arrange
        data = image(0xE7910002, 0xE7910102)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [(one.operand, one.text) for one in found],
            [(None, "ldr R0, [R1, R2]"), (None, "ldr R0, [R1, R2, lsl #2]")],
        )

    def test_the_indexing_decides_where_the_offset_is_written(self) -> None:
        # Arrange
        data = image(0xE4910004, 0xE5B10004, 0xE6B10002, 0xE6F10002)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found),
            [
                ("ldr", "ldr R0, [R1], #0x4"),
                ("ldr", "ldr R0, [R1, #0x4]!"),
                ("ldrt", "ldrt R0, [R1], R2"),
                ("ldrbt", "ldrbt R0, [R1], R2"),
            ],
        )


class BlockDataTransferTest(unittest.TestCase):
    def test_a_push_and_a_pop_read_as_the_datasheet_writes_them(self) -> None:
        # Arrange
        data = image(0xE92D4300, 0xE8BD8300)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found),
            [("stmdb", "stmdb SP!, {R8, R9, LR}"), ("ldmia", "ldmia SP!, {R8, R9, PC}")],
        )

    def test_the_other_modes_the_user_bank_and_an_empty_list_are_shown(self) -> None:
        # Arrange
        data = image(0xE8100001, 0xE9900001, 0xE8500001, 0xE8100000)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found),
            [
                ("ldmda", "ldmda R0, {R0}"),
                ("ldmib", "ldmib R0, {R0}"),
                ("ldmda", "ldmda R0, {R0}^"),
                ("ldmda", "ldmda R0, {}"),
            ],
        )


class TrapsAndCoprocessorsTest(unittest.TestCase):
    def test_a_software_interrupt_carries_its_comment_field(self) -> None:
        # Arrange
        data = image(0xEF123456)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [(one.mnemonic, one.operand, one.text) for one in found],
            [("swi", 0x123456, "swi 0x123456")],
        )

    def test_a_coprocessor_transfer_names_the_coprocessor_and_its_offset(self) -> None:
        # Arrange
        data = image(0xED910102, 0xEC910102, 0xED810102)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [(one.mnemonic, one.operand, one.text) for one in found],
            [
                ("ldc", 8, "ldc p1, c0, [R1, #0x8]"),
                ("ldc", 8, "ldc p1, c0, [R1], #0x8"),
                ("stc", 8, "stc p1, c0, [R1, #0x8]"),
            ],
        )

    def test_a_coprocessor_operation_and_both_register_moves_read_as_themselves(self) -> None:
        # Arrange
        data = image(0xEE123104, 0xEE213114, 0xEE313114)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found),
            [
                ("cdp", "cdp p1, 1, c3, c2, c4, 0"),
                ("mcr", "mcr p1, 1, R3, c1, c4, 0"),
                ("mrc", "mrc p1, 1, R3, c1, c4, 0"),
            ],
        )

    def test_the_undefined_row_and_a_word_outside_the_figure_are_shown(self) -> None:
        # Arrange
        data = image(0xE6000010, 0x000000D0)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [(one.kind, one.mnemonic, one.text) for one in found],
            [
                ("undefined", "undefined", "undefined 0xE6000010"),
                ("unspecified", "unspecified", "unspecifiedeq 0x000000D0"),
            ],
        )


class NoNumberTest(unittest.TestCase):
    def test_a_word_whose_operand_field_denotes_no_number_carries_none(self) -> None:
        # Arrange
        data = image(0xE0000291, 0xE1021093, 0xE8BD8300, 0xEE123104, 0xEE213114, 0xE6000010)

        # Act
        found = arm6.disassemble(data + image(0x000000D0))

        # Assert
        self.assertEqual([one.operand for one in found], [None] * 7)


class ConditionSpellingTest(unittest.TestCase):
    def test_a_condition_follows_the_operation_and_precedes_any_suffix(self) -> None:
        # Arrange
        data = image(0x15DB0020, 0x15910000, 0x12100001)

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            spelled(found),
            [
                ("ldrb", "ldrneb R0, [R11, #0x20]"),
                ("ldr", "ldrne R0, [R1]"),
                ("ands", "andnes R0, R0, #0x1"),
            ],
        )

    def test_every_condition_the_datasheet_numbers_renders(self) -> None:
        # Arrange
        data = image(*((code << 28) | 0x0A000000 for code in range(16)))

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(
            [one.text.split()[0] for one in found],
            [
                *("beq", "bne", "bcs", "bcc", "bmi", "bpl", "bvs", "bvc"),
                *("bhi", "bls", "bge", "blt", "bgt", "ble", "b", "bnv"),
            ],
        )

    def test_every_row_of_the_figure_has_a_kind(self) -> None:
        # Arrange
        data = image(
            *(0xE0000291, 0xE1021093, 0xE5100000, 0xE6000010, 0xE8100001, 0xEA000000),
            *(0xED910102, 0xEE123104, 0xEE313114, 0xEF123456, 0xE1A00000),
        )

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual({one.kind for one in found}, FIGURE_28_ROWS)


class WalkTest(unittest.TestCase):
    def test_a_walk_returns_every_instruction_in_order_past_a_return(self) -> None:
        # Arrange
        data = image(0xE3A08000, 0xE1A0F00E, 0xE5098000)

        # Act
        found = arm6.disassemble(data, address=0x100)

        # Assert
        self.assertEqual([one.address for one in found], [0x100, 0x104, 0x108])

    def test_a_walk_stops_at_the_count_it_was_given(self) -> None:
        # Arrange
        data = image(0xE3A08000, MOVE)

        # Act
        found = arm6.disassemble(data, count=1)

        # Assert
        self.assertEqual(len(found), 1)

    def test_a_walk_stops_when_the_image_runs_out(self) -> None:
        # Arrange
        data = image(0xE3A08000) + b"\x00\x00"

        # Act
        found = arm6.disassemble(data)

        # Assert
        self.assertEqual(len(found), 1)


class ReturnTest(unittest.TestCase):
    def test_moving_the_link_register_into_the_counter_is_a_return(self) -> None:
        # Arrange
        data = image(0xE3A08000, 0xE1A0F00E, MOVE)

        # Act
        found = arm6.disassemble(data, stop_at_return=True)

        # Assert
        self.assertEqual(len(found), 2)

    def test_loading_the_counter_off_the_stack_is_a_return(self) -> None:
        # Arrange
        data = image(0xE8BD8300, MOVE)

        # Act
        found = arm6.disassemble(data, stop_at_return=True)

        # Assert
        self.assertEqual(len(found), 1)

    def test_nothing_else_is_taken_for_a_return(self) -> None:
        # Arrange
        data = image(0xE8BD0300, 0xE92D8300, 0xE1A0F000, 0xE1A0000E, BRANCH, 0xE3A0F00E, MOVE)

        # Act
        found = arm6.disassemble(data, stop_at_return=True)

        # Assert
        self.assertEqual(len(found), 7)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import singlestep  # noqa: E402

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


class TheFilterTest(unittest.TestCase):
    def test_a_case_in_a_mode_this_part_has_is_kept(self) -> None:
        # Arrange
        one = case(0xE1A00001)

        # Act
        held = singlestep.excluded(one, "arm_data_proc_immediate")

        # Assert
        self.assertIsNone(held)

    def test_a_case_in_system_mode_is_excluded(self) -> None:
        # Arrange
        one = case(0xE1A00001)
        one = one._replace(initial=(*one.initial[:31], 0x0000001F, *one.initial[32:]))

        # Act
        held = singlestep.excluded(one, "arm_data_proc_immediate")

        # Assert
        self.assertEqual(held, "system mode")

    def test_a_multiply_whose_destination_differs_from_its_multiplicand_is_kept(self) -> None:
        # Arrange
        one = case(0xE0010293)

        # Act
        held = singlestep.excluded(one, "arm_mul_mla")

        # Assert
        self.assertIsNone(held)

    def test_a_multiply_whose_destination_is_its_multiplicand_is_excluded(self) -> None:
        # Arrange
        one = case(0xE0010291)

        # Act
        held = singlestep.excluded(one, "arm_mul_mla")

        # Assert
        self.assertEqual(held, "Rd equals Rm")

    def test_and_that_rule_applies_only_to_the_multiply_file(self) -> None:
        # Arrange
        one = case(0xE0010291)

        # Act
        held = singlestep.excluded(one, "arm_data_proc_immediate")

        # Assert
        self.assertIsNone(held)

    def test_a_block_transfer_naming_registers_is_kept(self) -> None:
        # Arrange
        one = case(0xE8910001)

        # Act
        held = singlestep.excluded(one, "arm_ldm_stm")

        # Assert
        self.assertIsNone(held)

    def test_a_block_transfer_naming_none_is_excluded(self) -> None:
        # Arrange
        one = case(0xE8910000)

        # Act
        held = singlestep.excluded(one, "arm_ldm_stm")

        # Assert
        self.assertEqual(held, "empty register list")

    def test_a_multiply_encoding_with_bit_five_set_is_excluded(self) -> None:
        # Arrange
        one = case(0xE00002B1)

        # Act
        held = singlestep.excluded(one, "arm_mul_mla")

        # Assert
        self.assertEqual(held, "undefined multiply encoding")

    def test_a_case_with_the_thumb_bit_set_is_excluded(self) -> None:
        # Arrange
        one = case(0xE1A00001)
        one = one._replace(initial=(*one.initial[:31], 0x000000F3, *one.initial[32:]))

        # Act
        held = singlestep.excluded(one, "arm_data_proc_immediate")

        # Assert
        self.assertEqual(held, "bit 5 of the CPSR set")

    def test_a_file_the_figure_has_no_row_for_is_dropped_whole(self) -> None:
        # Arrange
        stem = "arm_bx"

        # Act
        held = singlestep.dropped(stem)

        # Assert
        self.assertEqual(held, "no such row in Figure 28")

    def test_a_coprocessor_file_is_dropped_whole_too(self) -> None:
        # Arrange
        stem = "arm_cdp"

        # Act
        held = singlestep.dropped(stem)

        # Assert
        self.assertEqual(held, "no coprocessor attached")

    def test_a_file_this_part_does_have_a_row_for_is_not_dropped(self) -> None:
        # Arrange
        stem = "arm_b_bl"

        # Act
        held = singlestep.dropped(stem)

        # Assert
        self.assertIsNone(held)

    def test_the_fetch_list_leaves_out_every_file_dropped_whole(self) -> None:
        # Arrange
        whole = singlestep.WHOLE_FILES

        # Act
        held = singlestep.wanted()

        # Assert
        dropped = [one for one in held if any(name in one for name in whole)]
        self.assertEqual(dropped, [])

    def test_and_names_every_file_that_is_kept(self) -> None:
        # Arrange
        expected = len(singlestep.ARM_FILES) - len(singlestep.WHOLE_FILES)

        # Act
        held = singlestep.wanted()

        # Assert
        self.assertEqual(len(held), expected)

    def test_the_file_list_covers_the_whole_corpus(self) -> None:
        # Arrange
        files = len(singlestep.ARM_FILES)

        # Act
        record = singlestep.pinned()["suites"][0]

        # Assert
        self.assertEqual(files * record["casesPerFile"], record["armStateCases"])

    def test_asking_for_the_file_list_prints_it_and_exits_zero(self) -> None:
        # Arrange
        said: list[str] = []

        # Act
        held = singlestep.main(["--files"], say=said.append)

        # Assert
        self.assertEqual((held, len(said)), (0, len(singlestep.wanted())))

    def test_every_file_the_filter_drops_is_named_in_the_record(self) -> None:
        # Arrange
        dropped = set(singlestep.WHOLE_FILES)

        # Act
        record = singlestep.pinned()

        # Assert
        named = {one for entry in record["filter"]["wholeFiles"] for one in entry["files"]}
        self.assertEqual(named, dropped)


class ReadingABankedRegisterTest(unittest.TestCase):
    def test_a_low_register_comes_from_the_base_bank(self) -> None:
        # Arrange
        initial = state()
        initial[3] = 0xB3
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        # Act
        held = singlestep.visible_register(one, 3)

        # Assert
        self.assertEqual(held, 0xB3)

    def test_a_middle_register_comes_from_the_fiq_bank_in_fiq_mode(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.FIQ_LOW_AT + 1] = 0xF1
        initial[9] = 0xB1
        initial[singlestep.CPSR] = 0x000000D1
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        # Act
        held = singlestep.visible_register(one, 9)

        # Assert
        self.assertEqual(held, 0xF1)

    def test_and_from_the_base_bank_in_any_other(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.FIQ_LOW_AT + 1] = 0xF1
        initial[9] = 0xB1
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        # Act
        held = singlestep.visible_register(one, 9)

        # Assert
        self.assertEqual(held, 0xB1)

    def test_a_stack_pointer_comes_from_the_mode_s_own_bank(self) -> None:
        # Arrange
        initial = state()
        initial[singlestep.BANKS_AT["svc"]] = 0x5C
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        # Act
        held = singlestep.visible_register(one, 13)

        # Assert
        self.assertEqual(held, 0x5C)

    def test_and_from_the_base_bank_in_a_user_mode(self) -> None:
        # Arrange
        initial = state()
        initial[13] = 0xB13
        initial[singlestep.CPSR] = 0x00000010
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        # Act
        held = singlestep.visible_register(one, 13)

        # Assert
        self.assertEqual(held, 0xB13)

    def test_the_counter_comes_from_the_base_bank(self) -> None:
        # Arrange
        initial = state()
        initial[15] = 0x1008
        one = case(0xE1A00001)._replace(initial=tuple(initial))

        # Act
        held = singlestep.visible_register(one, 15)

        # Assert
        self.assertEqual(held, 0x1008)


class WhatIsLeftOutOfAComparisonTest(unittest.TestCase):
    def test_a_multiply_that_sets_flags_leaves_the_carry_out(self) -> None:
        # Arrange
        word = 0xE0100291

        # Act
        held = singlestep.uncomparable_bits(word)

        # Assert
        self.assertEqual(held, 1 << 29)

    def test_a_multiply_that_does_not_set_flags_leaves_nothing_out(self) -> None:
        # Arrange
        word = 0xE0000291

        # Act
        held = singlestep.uncomparable_bits(word)

        # Assert
        self.assertEqual(held, 0)

    def test_a_psr_write_leaves_the_reserved_region_out(self) -> None:
        # Arrange
        word = 0xE128F000

        # Act
        held = singlestep.uncomparable_bits(word)

        # Assert
        self.assertEqual(held, 0x0FFFFF00)

    def test_and_so_does_the_whole_form(self) -> None:
        # Arrange
        word = 0xE129F000

        # Act
        held = singlestep.uncomparable_bits(word)

        # Assert
        self.assertEqual(held, 0x0FFFFF00)

    def test_an_ordinary_instruction_leaves_nothing_out(self) -> None:
        # Arrange
        word = 0xE1A00001

        # Act
        held = singlestep.uncomparable_bits(word)

        # Assert
        self.assertEqual(held, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)

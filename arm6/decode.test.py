from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import disassemble  # noqa: E402
from conformance.printed import quote  # noqa: E402

UNSPECIFIED = "unspecified"

FIGURE_TWENTY_EIGHT = [
    "block data transfer",
    "branch",
    "coprocessor data operation",
    "coprocessor data transfer",
    "coprocessor register transfer",
    "data processing",
    "multiply",
    "single data swap",
    "single data transfer",
    "software interrupt",
    "undefined",
]

FIGURE_FIVE = [
    "EQ",
    "NE",
    "CS",
    "CC",
    "MI",
    "PL",
    "VS",
    "VC",
    "HI",
    "LS",
    "GE",
    "LT",
    "GT",
    "LE",
    "AL",
    "NV",
]


def kind(word: int) -> str:
    return str(disassemble(word.to_bytes(4, "little"))[0].kind)


def every_row_deciding_field() -> list[int]:
    return [0xE0000000 | high << 20 | low << 4 for high in range(0x100) for low in range(0x10)]


class TheElevenRowsFigureTwentyEightPrintsTest(unittest.TestCase):
    def test_there_are_eleven_of_them(self) -> None:
        # Arrange
        words = every_row_deciding_field()

        # Act
        held = {kind(word) for word in words} - {UNSPECIFIED}

        # Assert
        self.assertEqual(len(held), 11)

    def test_they_are_the_ones_the_figure_names(self) -> None:
        # Arrange
        words = every_row_deciding_field()

        # Act
        held = sorted({kind(word) for word in words} - {UNSPECIFIED})

        # Assert
        self.assertEqual(held, FIGURE_TWENTY_EIGHT)


class EachRowIsRecognisedTest(unittest.TestCase):
    def test_a_data_processing_word(self) -> None:
        # Arrange
        image = (0xE0812003).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "data processing")

    def test_a_multiply(self) -> None:
        # Arrange
        image = (0xE0010293).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "multiply")

    def test_a_multiply_accumulate(self) -> None:
        # Arrange
        image = (0xE0213495).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "multiply")

    def test_a_word_swap(self) -> None:
        # Arrange
        image = (0xE1012090).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "single data swap")

    def test_a_byte_swap(self) -> None:
        # Arrange
        image = (0xE1412090).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "single data swap")

    def test_a_load_register(self) -> None:
        # Arrange
        image = (0xE5912000).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "single data transfer")

    def test_a_store_register_with_a_shifted_register_offset(self) -> None:
        # Arrange
        image = (0xE7812102).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "single data transfer")

    def test_the_encoding_the_figure_marks_undefined(self) -> None:
        # Arrange
        image = (0xE6000010).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "undefined")

    def test_a_block_data_transfer(self) -> None:
        # Arrange
        image = (0xE8BD4000).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "block data transfer")

    def test_a_branch(self) -> None:
        # Arrange
        image = (0xEA000001).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "branch")

    def test_a_branch_with_link(self) -> None:
        # Arrange
        image = (0xEB000001).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "branch")

    def test_a_coprocessor_data_transfer(self) -> None:
        # Arrange
        image = (0xED912100).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "coprocessor data transfer")

    def test_a_coprocessor_data_operation(self) -> None:
        # Arrange
        image = (0xEE012103).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "coprocessor data operation")

    def test_a_coprocessor_register_transfer(self) -> None:
        # Arrange
        image = (0xEE112113).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "coprocessor register transfer")

    def test_a_software_interrupt(self) -> None:
        # Arrange
        image = (0xEF000000).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "software interrupt")


class TheRowsThatWouldOverlapAreTriedInTheRightOrderTest(unittest.TestCase):
    def test_a_multiply_is_not_read_as_data_processing(self) -> None:
        # Arrange
        image = (0xE0000091).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "multiply")

    def test_a_swap_is_not_read_as_data_processing_or_a_multiply(self) -> None:
        # Arrange
        image = (0xE1000090).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "single data swap")

    def test_the_undefined_row_is_not_read_as_a_single_data_transfer(self) -> None:
        # Arrange
        image = (0xE7000010).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "undefined")

    def test_but_a_shifted_register_offset_with_bit_four_clear_is_a_transfer(self) -> None:
        # Arrange
        image = (0xE7000000).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "single data transfer")

    def test_a_coprocessor_operation_with_bit_four_clear(self) -> None:
        # Arrange
        image = (0xEE000000).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "coprocessor data operation")

    def test_and_a_register_transfer_with_it_set(self) -> None:
        # Arrange
        image = (0xEE000010).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "coprocessor register transfer")


class WhatFigureTwentyEightDoesNotHaveTest(unittest.TestCase):
    def test_a_branch_and_exchange_falls_in_the_data_processing_row(self) -> None:
        # Arrange
        image = (0xE12FFF10).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "data processing")

    def test_a_halfword_load_is_an_encoding_the_figure_does_not_cover(self) -> None:
        # Arrange
        image = (0xE1D120B0).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, UNSPECIFIED)

    def test_a_signed_byte_load_is_one_too(self) -> None:
        # Arrange
        image = (0xE1D120D0).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, UNSPECIFIED)

    def test_a_long_multiply_is_not_read_as_a_multiply(self) -> None:
        # Arrange
        image = (0xE0812394).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, UNSPECIFIED)

    def test_nothing_the_figure_lacks_acquires_a_row(self) -> None:
        # Arrange
        absent = {"branch and exchange", "halfword transfer", "long multiply", "signed load"}

        # Act
        held = {kind(word) for word in every_row_deciding_field()}

        # Assert
        self.assertEqual(absent & held, set())


class TheConditionFieldTest(unittest.TestCase):
    def test_the_sixteen_codes_are_the_names_figure_five_prints(self) -> None:
        # Arrange
        image = b"".join((code << 28 | 0x01A00000).to_bytes(4, "little") for code in range(16))

        # Act
        held = [one.condition for one in disassemble(image)]

        # Assert
        self.assertEqual(held, FIGURE_FIVE)

    def test_the_condition_is_the_top_four_bits(self) -> None:
        # Arrange
        image = (0x0A000000).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].condition

        # Assert
        self.assertEqual(held, "EQ")

    def test_and_the_always_code_is_the_one_almost_everything_carries(self) -> None:
        # Arrange
        image = (0xEA000000).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].condition

        # Assert
        self.assertEqual(held, "AL")


class EncodingsTheDatasheetSaysDoNotTrapTest(unittest.TestCase):
    def test_a_multiply_with_bit_five_set_is_not_quietly_read_as_anything(self) -> None:
        # Arrange
        image = (0xE00002B1).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, UNSPECIFIED)

    def test_nor_is_one_with_bit_six_set(self) -> None:
        # Arrange
        image = (0xE00002D1).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, UNSPECIFIED)

    def test_a_register_shift_with_bit_seven_clear_is_still_data_processing(self) -> None:
        # Arrange
        image = (0xE0812013).to_bytes(4, "little")

        # Act
        held = disassemble(image)[0].kind

        # Assert
        self.assertEqual(held, "data processing")

    def test_these_are_kept_apart_from_the_row_that_does_trap(self) -> None:
        # Arrange
        traps = kind(0xE6000010)

        # Act
        does_not = disassemble((0xE00002B1).to_bytes(4, "little"))[0].kind

        # Assert
        self.assertNotEqual(traps, does_not, quote("undefinedNotTrapping"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

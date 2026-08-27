"""That every encoding lands in one of the eleven rows Figure 28 prints, and no other.

Figure 28 is the whole instruction set on one page, and what it does not have
decides as much as what it does. There is no halfword transfer row, no signed
load row, no long multiply row and no branch-and-exchange row, so four of the
files in the published conformance corpus describe encodings this part does not
have. That is rung one from the part's own sheet rather than an inference from
the architecture's history, and it is checked here.

The rows overlap in their top bits, so the order they are tried in is part of the
decoding rather than an implementation detail: multiply and swap both read as
data processing until their bottom byte is looked at.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import decode  # noqa: E402


class TheElevenRowsFigureTwentyEightPrintsTest(unittest.TestCase):
    def test_there_are_eleven_of_them(self) -> None:
        held = len(decode.KINDS)

        self.assertEqual(held, 11)

    def test_they_are_the_ones_the_figure_names(self) -> None:
        held = sorted(decode.KINDS)

        self.assertEqual(
            held,
            [
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
            ],
        )


class EachRowIsRecognisedTest(unittest.TestCase):
    def test_a_data_processing_word(self) -> None:
        held = decode.classify(0xE0812003)

        self.assertEqual(held, "data processing")

    def test_a_multiply(self) -> None:
        held = decode.classify(0xE0010293)

        self.assertEqual(held, "multiply")

    def test_a_multiply_accumulate(self) -> None:
        held = decode.classify(0xE0213495)

        self.assertEqual(held, "multiply")

    def test_a_word_swap(self) -> None:
        held = decode.classify(0xE1012090)

        self.assertEqual(held, "single data swap")

    def test_a_byte_swap(self) -> None:
        held = decode.classify(0xE1412090)

        self.assertEqual(held, "single data swap")

    def test_a_load_register(self) -> None:
        held = decode.classify(0xE5912000)

        self.assertEqual(held, "single data transfer")

    def test_a_store_register_with_a_shifted_register_offset(self) -> None:
        held = decode.classify(0xE7812102)

        self.assertEqual(held, "single data transfer")

    def test_the_encoding_the_figure_marks_undefined(self) -> None:
        held = decode.classify(0xE6000010)

        self.assertEqual(held, "undefined")

    def test_a_block_data_transfer(self) -> None:
        held = decode.classify(0xE8BD4000)

        self.assertEqual(held, "block data transfer")

    def test_a_branch(self) -> None:
        held = decode.classify(0xEA000001)

        self.assertEqual(held, "branch")

    def test_a_branch_with_link(self) -> None:
        held = decode.classify(0xEB000001)

        self.assertEqual(held, "branch")

    def test_a_coprocessor_data_transfer(self) -> None:
        held = decode.classify(0xED912100)

        self.assertEqual(held, "coprocessor data transfer")

    def test_a_coprocessor_data_operation(self) -> None:
        held = decode.classify(0xEE012103)

        self.assertEqual(held, "coprocessor data operation")

    def test_a_coprocessor_register_transfer(self) -> None:
        held = decode.classify(0xEE112113)

        self.assertEqual(held, "coprocessor register transfer")

    def test_a_software_interrupt(self) -> None:
        held = decode.classify(0xEF000000)

        self.assertEqual(held, "software interrupt")


class TheRowsThatWouldOverlapAreTriedInTheRightOrderTest(unittest.TestCase):
    def test_a_multiply_is_not_read_as_data_processing(self) -> None:
        held = decode.classify(0xE0000091)

        self.assertEqual(held, "multiply")

    def test_a_swap_is_not_read_as_data_processing(self) -> None:
        held = decode.classify(0xE1000090)

        self.assertEqual(held, "single data swap")

    def test_a_swap_is_not_read_as_a_multiply(self) -> None:
        held = decode.classify(0xE1000090)

        self.assertNotEqual(held, "multiply")

    def test_the_undefined_row_is_not_read_as_a_single_data_transfer(self) -> None:
        held = decode.classify(0xE7000010)

        self.assertEqual(held, "undefined")

    def test_but_a_shifted_register_offset_with_bit_four_clear_is_a_transfer(self) -> None:
        held = decode.classify(0xE7000000)

        self.assertEqual(held, "single data transfer")

    def test_a_coprocessor_operation_and_a_register_transfer_differ_in_bit_four(self) -> None:
        held = (decode.classify(0xEE000000), decode.classify(0xEE000010))

        self.assertEqual(held, ("coprocessor data operation", "coprocessor register transfer"))


class WhatFigureTwentyEightDoesNotHaveTest(unittest.TestCase):
    def test_a_branch_and_exchange_falls_in_the_data_processing_row(self) -> None:
        held = decode.classify(0xE12FFF10)

        self.assertEqual(held, "data processing")

    def test_a_halfword_load_is_an_encoding_the_figure_does_not_cover(self) -> None:
        held = decode.classify(0xE1D120B0)

        self.assertEqual(held, decode.UNSPECIFIED)

    def test_a_signed_byte_load_is_one_too(self) -> None:
        held = decode.classify(0xE1D120D0)

        self.assertEqual(held, decode.UNSPECIFIED)

    def test_a_long_multiply_is_not_read_as_a_multiply(self) -> None:
        held = decode.classify(0xE0812394)

        self.assertEqual(held, decode.UNSPECIFIED)

    def test_nothing_the_figure_lacks_acquires_a_row(self) -> None:
        absent = {"branch and exchange", "halfword transfer", "long multiply", "signed load"}

        overlap = absent & set(decode.KINDS)

        self.assertEqual(overlap, set())

    def test_an_encoding_outside_the_figure_is_not_one_of_its_rows(self) -> None:
        held = decode.UNSPECIFIED in decode.KINDS

        self.assertFalse(held)


class TheConditionFieldTest(unittest.TestCase):
    def test_there_are_sixteen_codes(self) -> None:
        held = len(decode.CONDITIONS)

        self.assertEqual(held, 16)

    def test_they_are_the_names_figure_five_prints(self) -> None:
        held = decode.CONDITIONS

        self.assertEqual(
            held,
            (
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
            ),
        )

    def test_the_condition_is_the_top_four_bits(self) -> None:
        held = decode.condition_of(0x0A000000)

        self.assertEqual(held, "EQ")

    def test_and_the_always_code_is_the_one_almost_everything_carries(self) -> None:
        held = decode.condition_of(0xEA000000)

        self.assertEqual(held, "AL")


class ReadingWithoutRunningTest(unittest.TestCase):
    def test_a_word_is_described_by_its_row_and_its_condition(self) -> None:
        held = decode.describe(0x0AFFFFFE)

        self.assertEqual(held, "EQ branch")

    def test_an_unconditional_word_still_names_its_condition(self) -> None:
        held = decode.describe(0xEF000000)

        self.assertEqual(held, "AL software interrupt")


class EncodingsTheDatasheetSaysDoNotTrapTest(unittest.TestCase):
    def test_a_multiply_with_bit_five_set_is_not_a_multiply(self) -> None:
        held = decode.classify(0xE00002B1)

        self.assertNotEqual(held, "multiply")

    def test_and_it_is_not_quietly_read_as_data_processing_either(self) -> None:
        held = decode.classify(0xE00002B1)

        self.assertEqual(held, decode.UNSPECIFIED)

    def test_nor_is_one_with_bit_six_set(self) -> None:
        held = decode.classify(0xE00002D1)

        self.assertEqual(held, decode.UNSPECIFIED)

    def test_these_are_kept_apart_from_the_row_that_does_trap(self) -> None:
        traps = decode.classify(0xE6000010)
        does_not = decode.classify(0xE00002B1)

        self.assertNotEqual(traps, does_not)

    def test_a_register_shift_with_bit_seven_clear_is_still_data_processing(self) -> None:
        held = decode.classify(0xE0812013)

        self.assertEqual(held, "data processing")


if __name__ == "__main__":
    unittest.main(verbosity=2)

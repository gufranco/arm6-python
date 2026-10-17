from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import BadWaits, Cpu, Cycles, Memory, Waits, WaitsRequired  # noqa: E402
from conformance.printed import quote  # noqa: E402

MULTIPLY_R0_R1_R2 = 0xE0000291

FLAT = {"sequential": 1, "nonsequential": 1, "internal": 1, "coprocessor": 1}


class CountsInTheDocumentsTermsTest(unittest.TestCase):
    def test_a_tally_keeps_each_type_apart(self) -> None:
        # Arrange
        tally = Cycles(s=2, n=1, i=16, c=1)

        # Act
        parts = (tally.s, tally.n, tally.i, tally.c)

        # Assert
        self.assertEqual(parts, (2, 1, 16, 1))

    def test_a_tally_built_with_nothing_counts_nothing(self) -> None:
        # Arrange
        tally = Cycles()

        # Act
        parts = (tally.s, tally.n, tally.i, tally.c)

        # Assert
        self.assertEqual(parts, (0, 0, 0, 0))

    def test_the_total_is_the_count_with_nwait_tied_high(self) -> None:
        # Arrange
        tally = Cycles(s=2, n=1, i=16, c=1)

        # Act
        total = tally.total

        # Assert
        self.assertEqual(total, 20)

    def test_the_multiply_worst_case_the_datasheet_names_is_seventeen_cycles(self) -> None:
        # Arrange
        image = MULTIPLY_R0_R1_R2.to_bytes(4, "little")
        part = Cpu("arm60", Memory(image=image, fill=0), fill=0).reset()
        part.registers.write(2, 0x80000000)

        # Act
        spent = part.step()

        # Assert
        self.assertEqual((spent, part.spent), (17, Cycles(s=1, i=16)))

    def test_a_tally_says_what_it_holds_when_printed(self) -> None:
        # Arrange
        tally = Cycles(s=1, n=2, i=3, c=4)

        # Act
        shown = repr(tally)

        # Assert
        self.assertEqual(shown, "Cycles(s=1, n=2, i=3, c=4)")

    def test_two_tallies_holding_the_same_counts_are_equal(self) -> None:
        # Arrange
        first = Cycles(s=1, n=2)

        # Act
        same = first == Cycles(s=1, n=2)

        # Assert
        self.assertTrue(same)

    def test_and_one_holding_different_counts_is_not(self) -> None:
        # Arrange
        first = Cycles(s=1, n=2)

        # Act
        same = first == Cycles(s=2, n=1)

        # Assert
        self.assertFalse(same)

    def test_a_tally_is_not_equal_to_the_bare_number_it_totals(self) -> None:
        # Arrange
        tally = Cycles(s=3)

        # Act
        same = tally == 3

        # Assert
        self.assertFalse(same)

    def test_a_tally_can_be_kept_in_a_set(self) -> None:
        # Arrange
        run = [Cycles(s=1, n=1), Cycles(s=1, n=1), Cycles(i=2)]

        # Act
        distinct = len(set(run))

        # Assert
        self.assertEqual(distinct, 2)


class TalliesAddUpTest(unittest.TestCase):
    def test_two_tallies_add_type_by_type(self) -> None:
        # Arrange
        first = Cycles(s=1, n=1)
        second = Cycles(s=2, i=3)

        # Act
        together = first + second

        # Assert
        self.assertEqual((together.s, together.n, together.i, together.c), (3, 1, 3, 0))

    def test_and_the_sum_is_still_a_tally(self) -> None:
        # Arrange
        first = Cycles(s=1)

        # Act
        together = first + Cycles(n=1)

        # Assert
        self.assertIs(type(together), Cycles)

    def test_adding_a_plain_number_is_refused_rather_than_guessed_at(self) -> None:
        # Arrange
        tally = Cycles(s=1)

        # Act
        with self.assertRaises(TypeError) as caught:
            tally + 1

        # Assert
        self.assertIn("Cycles", str(caught.exception))

    def test_a_run_of_tallies_sums_from_an_empty_one(self) -> None:
        # Arrange
        run = [Cycles(s=1), Cycles(n=1), Cycles(i=2)]

        # Act
        together = sum(run, Cycles())

        # Assert
        self.assertEqual((together.s, together.n, together.i), (1, 1, 2))

    def test_the_running_total_of_a_part_adds_each_instruction_s_cost(self) -> None:
        # Arrange
        part = Cpu("arm60", fill=0).reset()

        # Act
        part.run_for(3)

        # Assert
        self.assertEqual(part.tally, Cycles(s=7, n=1, i=0, c=0))


class RefusesToInventABoardTest(unittest.TestCase):
    def test_asking_for_ticks_without_saying_what_the_board_costs_is_refused(self) -> None:
        # Arrange
        tally = Cycles(s=1, n=1)

        # Act
        with self.assertRaises(WaitsRequired) as caught:
            tally.ticks(None)

        # Assert
        self.assertIsInstance(caught.exception, WaitsRequired)

    def test_and_the_refusal_says_why_rather_than_naming_a_type(self) -> None:
        # Arrange
        tally = Cycles(s=1)

        # Act
        with self.assertRaises(WaitsRequired) as caught:
            tally.ticks(None)

        # Assert
        self.assertIn("Nwait", str(caught.exception))

    def test_a_board_that_states_its_costs_gets_a_tick_count(self) -> None:
        # Arrange
        tally = Cycles(s=2, n=1, i=1, c=1)

        # Act
        ticks = tally.ticks(Waits(sequential=1, nonsequential=3, internal=1, coprocessor=1))

        # Assert
        self.assertEqual(ticks, 2 + 3 + 1 + 1)

    def test_a_memory_clock_at_half_the_processor_clock_is_expressible(self) -> None:
        # Arrange
        tally = Cycles(s=4, n=1, i=2, c=0)

        # Act
        ticks = tally.ticks(Waits(sequential=2, nonsequential=2, internal=1, coprocessor=1))

        # Assert
        self.assertEqual(ticks, 8 + 2 + 2)

    def test_a_coprocessor_cycle_is_charged_at_its_own_figure(self) -> None:
        # Arrange
        tally = Cycles(c=3)

        # Act
        ticks = tally.ticks(Waits(sequential=1, nonsequential=1, internal=1, coprocessor=5))

        # Assert
        self.assertEqual(ticks, 15)

    def test_a_cycle_costing_less_than_one_mclk_is_refused(self) -> None:
        # Arrange
        figures = {**FLAT, "sequential": 0}

        # Act
        with self.assertRaises(BadWaits) as caught:
            Waits(**figures)

        # Assert
        self.assertIn("sequential is 0", str(caught.exception))

    def test_and_so_is_a_negative_one(self) -> None:
        # Arrange
        figures = {**FLAT, "nonsequential": -1}

        # Act
        with self.assertRaises(BadWaits) as caught:
            Waits(**figures)

        # Assert
        self.assertIn("nonsequential is -1", str(caught.exception))

    def test_and_the_refusal_names_the_line_that_was_wrong(self) -> None:
        # Arrange
        figures = {**FLAT, "internal": 0}

        # Act
        with self.assertRaises(BadWaits) as caught:
            Waits(**figures)

        # Assert
        self.assertIn("internal", str(caught.exception))

    def test_and_the_last_line_is_checked_as_well_as_the_first(self) -> None:
        # Arrange
        figures = {**FLAT, "coprocessor": 0}

        # Act
        with self.assertRaises(BadWaits) as caught:
            Waits(**figures)

        # Assert
        self.assertIn("coprocessor", str(caught.exception))

    def test_a_board_with_no_wait_states_is_a_configuration_the_pin_table_allows(self) -> None:
        # Arrange
        tally = Cycles(s=3, n=2, i=1, c=1)

        # Act
        ticks = tally.ticks(Waits(sequential=1, nonsequential=1, internal=1, coprocessor=1))

        # Assert
        self.assertEqual(ticks, tally.total, quote("nwaitTiedHigh"))

    def test_a_board_says_what_it_costs_when_printed(self) -> None:
        # Arrange
        waits = Waits(sequential=1, nonsequential=2, internal=1, coprocessor=1)

        # Act
        shown = repr(waits)

        # Assert
        self.assertEqual(shown, "Waits(sequential=1, nonsequential=2, internal=1, coprocessor=1)")


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_a_tally_refuses_a_name_it_does_not_have(self) -> None:
        # Arrange
        tally = Cycles(s=1)

        # Act
        with self.assertRaises(AttributeError) as caught:
            tally.q = 1

        # Assert
        self.assertIn("measurement", str(caught.exception))

    def test_and_so_does_a_board(self) -> None:
        # Arrange
        waits = Waits(**FLAT)

        # Act
        with self.assertRaises(AttributeError) as caught:
            waits.q = 1

        # Assert
        self.assertIn("measurement", str(caught.exception))

    def test_a_tally_refuses_a_write_to_a_name_it_does_have(self) -> None:
        # Arrange
        tally = Cycles(s=1)

        # Act
        with self.assertRaises(AttributeError):
            tally.s = 2

        # Assert
        self.assertEqual(tally.s, 1)

    def test_and_a_board_refuses_one_too(self) -> None:
        # Arrange
        waits = Waits(**FLAT)

        # Act
        with self.assertRaises(AttributeError):
            waits.sequential = 2

        # Assert
        self.assertEqual(waits.sequential, 1)


class ATallyIsAMeasurementRatherThanAVariableTest(unittest.TestCase):
    def test_a_name_cannot_be_deleted_from_a_tally(self) -> None:
        # Arrange
        tally = Cycles(s=1)

        # Act
        with self.assertRaises(AttributeError):
            del tally.s

        # Assert
        self.assertEqual(tally.s, 1)

    def test_nor_from_a_board(self) -> None:
        # Arrange
        waits = Waits(**FLAT)

        # Act
        with self.assertRaises(AttributeError):
            del waits.sequential

        # Assert
        self.assertEqual(waits.sequential, 1)

    def test_a_plain_number_on_the_left_is_refused_as_well(self) -> None:
        # Arrange
        tally = Cycles(s=1)

        # Act
        with self.assertRaises(TypeError) as caught:
            1 + tally

        # Assert
        self.assertIn("Cycles", str(caught.exception))

    def test_a_run_of_tallies_sums_without_being_given_a_start(self) -> None:
        # Arrange
        run = [Cycles(s=1), Cycles(n=2)]

        # Act
        together = sum(run)

        # Assert
        self.assertEqual(together, Cycles(s=1, n=2))


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""That a cycle tally counts in the manufacturer's own terms and converts in nobody's.

ARM60 Table 3 gives four cycle types, decided by `Nmreq` and `seq`, and Table 20
states every instruction's cost in those terms rather than in ticks. Section 8.6
then says the clock may be stretched without limit and that `Nwait` may insert
whole `mclk` cycles, which makes the number of ticks a cycle takes a fact about
the board rather than about the part.

So the tally counts S, N, I and C, and refuses to become a tick count until a
caller says what their own memory system costs.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6.errors import BadWaits, WaitsRequired  # noqa: E402
from arm6.tally import Cycles, Waits  # noqa: E402


class CountsInTheDocumentsTermsTest(unittest.TestCase):
    def test_a_tally_keeps_each_type_apart(self) -> None:
        tally = Cycles(s=2, n=1, i=16, c=1)

        parts = (tally.s, tally.n, tally.i, tally.c)

        self.assertEqual(parts, (2, 1, 16, 1))

    def test_a_tally_built_with_nothing_counts_nothing(self) -> None:
        tally = Cycles()

        parts = (tally.s, tally.n, tally.i, tally.c)

        self.assertEqual(parts, (0, 0, 0, 0))

    def test_the_total_is_the_count_with_nwait_tied_high(self) -> None:
        tally = Cycles(s=2, n=1, i=16, c=1)

        total = tally.total

        self.assertEqual(total, 20)

    def test_the_multiply_worst_case_the_datasheet_names_is_seventeen_cycles(self) -> None:
        tally = Cycles(s=1, i=16)

        total = tally.total

        self.assertEqual(total, 17)

    def test_a_tally_says_what_it_holds_when_printed(self) -> None:
        tally = Cycles(s=1, n=2, i=3, c=4)

        shown = repr(tally)

        self.assertEqual(shown, "Cycles(s=1, n=2, i=3, c=4)")

    def test_two_tallies_holding_the_same_counts_are_equal(self) -> None:
        first = Cycles(s=1, n=2)

        same = first == Cycles(s=1, n=2)

        self.assertTrue(same)

    def test_and_one_holding_different_counts_is_not(self) -> None:
        first = Cycles(s=1, n=2)

        same = first == Cycles(s=2, n=1)

        self.assertFalse(same)

    def test_a_tally_is_not_equal_to_the_bare_number_it_totals(self) -> None:
        tally = Cycles(s=3)

        same = tally == 3

        self.assertFalse(same)

    def test_a_tally_can_be_kept_in_a_set(self) -> None:
        held = {Cycles(s=1, n=1), Cycles(s=1, n=1), Cycles(i=2)}

        distinct = len(held)

        self.assertEqual(distinct, 2)


class TalliesAddUpTest(unittest.TestCase):
    def test_two_tallies_add_type_by_type(self) -> None:
        first = Cycles(s=1, n=1)
        second = Cycles(s=2, i=3)

        together = first + second

        self.assertEqual((together.s, together.n, together.i, together.c), (3, 1, 3, 0))

    def test_and_the_sum_is_still_a_tally(self) -> None:
        together = Cycles(s=1) + Cycles(n=1)

        kind = type(together)

        self.assertIs(kind, Cycles)

    def test_adding_a_plain_number_is_refused_rather_than_guessed_at(self) -> None:
        tally = Cycles(s=1)

        with self.assertRaises(TypeError):
            tally + 1

    def test_a_run_of_tallies_sums_from_an_empty_one(self) -> None:
        run = [Cycles(s=1), Cycles(n=1), Cycles(i=2)]

        together = sum(run, Cycles())

        self.assertEqual((together.s, together.n, together.i), (1, 1, 2))


class RefusesToInventABoardTest(unittest.TestCase):
    def test_asking_for_ticks_without_saying_what_the_board_costs_is_refused(self) -> None:
        tally = Cycles(s=1, n=1)

        with self.assertRaises(WaitsRequired):
            tally.ticks(None)

    def test_and_the_refusal_says_why_rather_than_naming_a_type(self) -> None:
        tally = Cycles(s=1)

        with self.assertRaises(WaitsRequired) as caught:
            tally.ticks(None)

        self.assertIn("Nwait", str(caught.exception))

    def test_a_board_that_states_its_costs_gets_a_tick_count(self) -> None:
        tally = Cycles(s=2, n=1, i=1, c=1)

        ticks = tally.ticks(Waits(sequential=1, nonsequential=3, internal=1, coprocessor=1))

        self.assertEqual(ticks, 2 + 3 + 1 + 1)

    def test_a_memory_clock_at_half_the_processor_clock_is_expressible(self) -> None:
        tally = Cycles(s=4, n=1, i=2, c=0)

        ticks = tally.ticks(Waits(sequential=2, nonsequential=2, internal=1, coprocessor=1))

        self.assertEqual(ticks, 8 + 2 + 2)

    def test_a_cycle_costing_less_than_one_mclk_is_refused(self) -> None:
        with self.assertRaises(BadWaits):
            Waits(sequential=0, nonsequential=1, internal=1, coprocessor=1)

    def test_and_so_is_a_negative_one(self) -> None:
        with self.assertRaises(BadWaits):
            Waits(sequential=1, nonsequential=-1, internal=1, coprocessor=1)

    def test_and_the_refusal_names_the_line_that_was_wrong(self) -> None:
        with self.assertRaises(BadWaits) as caught:
            Waits(sequential=1, nonsequential=1, internal=0, coprocessor=1)

        self.assertIn("internal", str(caught.exception))

    def test_and_the_last_line_is_checked_as_well_as_the_first(self) -> None:
        with self.assertRaises(BadWaits) as caught:
            Waits(sequential=1, nonsequential=1, internal=1, coprocessor=0)

        self.assertIn("coprocessor", str(caught.exception))

    def test_a_board_with_no_wait_states_is_a_configuration_the_pin_table_allows(self) -> None:
        tally = Cycles(s=3, n=2, i=1, c=1)

        ticks = tally.ticks(Waits(sequential=1, nonsequential=1, internal=1, coprocessor=1))

        self.assertEqual(ticks, tally.total)

    def test_a_board_says_what_it_costs_when_printed(self) -> None:
        waits = Waits(sequential=1, nonsequential=2, internal=1, coprocessor=1)

        shown = repr(waits)

        self.assertEqual(shown, "Waits(sequential=1, nonsequential=2, internal=1, coprocessor=1)")


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_a_tally_refuses_a_name_it_does_not_have(self) -> None:
        tally = Cycles(s=1)

        with self.assertRaises(AttributeError):
            tally.q = 1

    def test_and_so_does_a_board(self) -> None:
        waits = Waits(sequential=1, nonsequential=1, internal=1, coprocessor=1)

        with self.assertRaises(AttributeError):
            waits.q = 1

    def test_a_tally_refuses_a_write_to_a_name_it_does_have(self) -> None:
        tally = Cycles(s=1)

        with self.assertRaises(AttributeError):
            tally.s = 2

    def test_and_a_board_refuses_one_too(self) -> None:
        waits = Waits(sequential=1, nonsequential=1, internal=1, coprocessor=1)

        with self.assertRaises(AttributeError):
            waits.sequential = 2


class ATallyIsAMeasurementRatherThanAVariableTest(unittest.TestCase):
    def test_a_name_cannot_be_deleted_from_a_tally(self) -> None:
        tally = Cycles(s=1)

        with self.assertRaises(AttributeError):
            del tally.s

    def test_nor_from_a_board(self) -> None:
        waits = Waits(sequential=1, nonsequential=1, internal=1, coprocessor=1)

        with self.assertRaises(AttributeError):
            del waits.sequential

    def test_a_plain_number_on_the_left_is_refused_as_well(self) -> None:
        tally = Cycles(s=1)

        with self.assertRaises(TypeError):
            1 + tally

    def test_a_run_of_tallies_sums_without_being_given_a_start(self) -> None:
        run = [Cycles(s=1), Cycles(n=2)]

        together = sum(run)

        self.assertEqual(together, Cycles(s=1, n=2))


if __name__ == "__main__":
    unittest.main(verbosity=2)

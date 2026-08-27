"""That a recorded cycle carries what chapter 10's tables print in that row.

The header of chapter 10 states which of the columns are pipelined and by how
much: `Nmreq` and `seq` appear up to one cycle ahead of the cycle they apply to,
so they forecast the next one, while the address, `Nbw`, `Nrw` and `Nopc` appear
up to half a cycle ahead and describe the cycle they are printed in. A record
that flattened those into one column would lose the only thing the memory system
uses to decide whether it can run a page mode access.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6.bus import COPROCESSOR, INTERNAL, NONSEQUENTIAL, SEQUENTIAL, Cycle, Recorder  # noqa: E402


class TheFourTypesTableThreeDefinesTest(unittest.TestCase):
    def test_a_non_sequential_cycle_is_nmreq_low_and_seq_low(self) -> None:
        held = (NONSEQUENTIAL.nmreq, NONSEQUENTIAL.seq)

        self.assertEqual(held, (0, 0))

    def test_a_sequential_cycle_is_nmreq_low_and_seq_high(self) -> None:
        held = (SEQUENTIAL.nmreq, SEQUENTIAL.seq)

        self.assertEqual(held, (0, 1))

    def test_an_internal_cycle_is_nmreq_high_and_seq_low(self) -> None:
        held = (INTERNAL.nmreq, INTERNAL.seq)

        self.assertEqual(held, (1, 0))

    def test_a_coprocessor_register_transfer_is_both_high(self) -> None:
        held = (COPROCESSOR.nmreq, COPROCESSOR.seq)

        self.assertEqual(held, (1, 1))

    def test_the_four_encodings_are_all_different(self) -> None:
        held = {(one.nmreq, one.seq) for one in (SEQUENTIAL, NONSEQUENTIAL, INTERNAL, COPROCESSOR)}

        self.assertEqual(len(held), 4)

    def test_an_internal_cycle_requests_no_memory(self) -> None:
        held = INTERNAL.touches_memory

        self.assertFalse(held)

    def test_and_a_sequential_one_does(self) -> None:
        held = SEQUENTIAL.touches_memory

        self.assertTrue(held)


class WhatOneRecordedCycleCarriesTest(unittest.TestCase):
    def test_it_carries_the_address_driven_in_that_cycle(self) -> None:
        held = Cycle(SEQUENTIAL, address=0x1008, nopc=0)

        self.assertEqual(held.address, 0x1008)

    def test_an_opcode_fetch_drives_nopc_low(self) -> None:
        held = Cycle(SEQUENTIAL, address=0, nopc=0)

        self.assertEqual(held.nopc, 0)

    def test_a_data_transfer_drives_it_high(self) -> None:
        held = Cycle(NONSEQUENTIAL, address=0, nopc=1)

        self.assertEqual(held.nopc, 1)

    def test_a_word_access_drives_nbw_high(self) -> None:
        held = Cycle(NONSEQUENTIAL, address=0, nopc=1)

        self.assertEqual(held.nbw, 1)

    def test_a_byte_access_drives_it_low(self) -> None:
        held = Cycle(NONSEQUENTIAL, address=0, nopc=1, nbw=0)

        self.assertEqual(held.nbw, 0)

    def test_a_write_drives_nrw_high(self) -> None:
        held = Cycle(NONSEQUENTIAL, address=0, nopc=1, nrw=1)

        self.assertEqual(held.nrw, 1)

    def test_the_lock_line_is_low_except_during_a_swap(self) -> None:
        held = Cycle(NONSEQUENTIAL, address=0, nopc=1)

        self.assertEqual(held.lock, 0)

    def test_a_cycle_says_what_it_was_when_printed(self) -> None:
        held = repr(Cycle(SEQUENTIAL, address=0x20, nopc=0))

        self.assertEqual(held, "Cycle(S, address=0x00000020, nopc=0)")


class TheForecastIsWhatTableTwentyCountsTest(unittest.TestCase):
    def test_a_branch_costs_two_sequential_and_one_non_sequential(self) -> None:
        held = Recorder()
        held.add(Cycle(NONSEQUENTIAL, address=0x08, nopc=0))
        held.add(Cycle(SEQUENTIAL, address=0x40, nopc=0))
        held.add(Cycle(SEQUENTIAL, address=0x44, nopc=0))

        spent = held.spent()

        self.assertEqual((spent.s, spent.n, spent.i, spent.c), (2, 1, 0, 0))

    def test_a_store_register_costs_two_non_sequential(self) -> None:
        held = Recorder()
        held.add(Cycle(NONSEQUENTIAL, address=0x08, nopc=0))
        held.add(Cycle(NONSEQUENTIAL, address=0x40, nopc=1, nrw=1))

        spent = held.spent()

        self.assertEqual((spent.s, spent.n, spent.i, spent.c), (0, 2, 0, 0))

    def test_the_longest_multiply_costs_one_sequential_and_sixteen_internal(self) -> None:
        held = Recorder()
        for _ in range(16):
            held.add(Cycle(INTERNAL, address=0x0C, nopc=1))
        held.add(Cycle(SEQUENTIAL, address=0x0C, nopc=1))

        spent = held.spent()

        self.assertEqual((spent.s, spent.i), (1, 16))

    def test_a_recorder_with_nothing_in_it_reports_nothing(self) -> None:
        held = Recorder()

        spent = held.spent()

        self.assertEqual(spent.total, 0)

    def test_the_recorder_hands_back_the_cycles_it_was_given(self) -> None:
        held = Recorder()
        held.add(Cycle(SEQUENTIAL, address=4, nopc=0))

        kept = held.cycles

        self.assertEqual(len(kept), 1)

    def test_clearing_it_leaves_nothing_behind(self) -> None:
        held = Recorder()
        held.add(Cycle(SEQUENTIAL, address=4, nopc=0))

        held.clear()

        self.assertEqual(held.cycles, [])


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_a_cycle_refuses_a_name_it_does_not_have(self) -> None:
        held = Cycle(SEQUENTIAL, address=0, nopc=0)

        with self.assertRaises(AttributeError):
            held.q = 1  # type: ignore[attr-defined]

    def test_a_recorder_refuses_one_too(self) -> None:
        held = Recorder()

        with self.assertRaises(AttributeError):
            held.q = 1  # type: ignore[attr-defined]

    def test_a_type_refuses_one_as_well(self) -> None:
        with self.assertRaises(AttributeError):
            SEQUENTIAL.q = 1


class ACycleTypeNamesItselfTest(unittest.TestCase):
    def test_a_type_says_which_letter_it_is_when_printed(self) -> None:
        held = repr(SEQUENTIAL)

        self.assertEqual(held, "CycleType(S)")

    def test_and_each_of_the_four_prints_a_different_letter(self) -> None:
        held = {repr(one) for one in (SEQUENTIAL, NONSEQUENTIAL, INTERNAL, COPROCESSOR)}

        self.assertEqual(len(held), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)

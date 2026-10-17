from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import Cpu, Memory  # noqa: E402

BRANCH = 0xEA00000E
STORE_R0_TO_R1 = 0xE5810000
LOAD_R0_FROM_R1 = 0xE5910000
LOAD_BYTE_R0_FROM_R1 = 0xE5D10000
SWAP_R0_R2_AT_R1 = 0xE1010092
MULTIPLY_R0_R1_R2 = 0xE0000291
ANDEQ_R0_R0_R0 = 0x00000000

DATA = 0x100
LONGEST_MULTIPLIER = 0x80000000


def ready(word: int) -> Cpu:
    part = Cpu("arm60", Memory(image=word.to_bytes(4, "little"), fill=0), fill=0).reset()
    part.registers.write(1, DATA)
    part.registers.write(2, LONGEST_MULTIPLIER)
    return part


def rows_of(word: int) -> list[Any]:
    part = ready(word)
    part.step()
    return list(part.bus.cycles)


def kind_of(word: int, row: int) -> Any:
    return rows_of(word)[row].kind


def data_row(part: Cpu) -> Any:
    return next(one for one in part.bus.cycles if one.nopc == 1 and one.address == DATA)


class TheFourTypesTableThreeDefinesTest(unittest.TestCase):
    def test_a_non_sequential_cycle_is_nmreq_low_and_seq_low(self) -> None:
        # Arrange
        part = ready(BRANCH)

        # Act
        part.step()

        # Assert
        kind = part.bus.cycles[0].kind
        self.assertEqual((kind.letter, kind.nmreq, kind.seq), ("N", 0, 0))

    def test_a_sequential_cycle_is_nmreq_low_and_seq_high(self) -> None:
        # Arrange
        part = ready(BRANCH)

        # Act
        part.step()

        # Assert
        kind = part.bus.cycles[1].kind
        self.assertEqual((kind.letter, kind.nmreq, kind.seq), ("S", 0, 1))

    def test_an_internal_cycle_is_nmreq_high_and_seq_low(self) -> None:
        # Arrange
        part = ready(MULTIPLY_R0_R1_R2)

        # Act
        part.step()

        # Assert
        kind = part.bus.cycles[0].kind
        self.assertEqual((kind.letter, kind.nmreq, kind.seq), ("I", 1, 0))

    def test_the_three_types_a_part_with_no_coprocessor_drives_are_all_different(self) -> None:
        # Arrange
        words = (BRANCH, MULTIPLY_R0_R1_R2, STORE_R0_TO_R1)

        # Act
        held = {(row.kind.nmreq, row.kind.seq) for word in words for row in rows_of(word)}

        # Assert
        self.assertEqual(held, {(0, 0), (0, 1), (1, 0)})

    def test_an_internal_cycle_requests_no_memory(self) -> None:
        # Arrange
        part = ready(MULTIPLY_R0_R1_R2)

        # Act
        part.step()

        # Assert
        self.assertFalse(part.bus.cycles[0].kind.touches_memory)

    def test_and_a_sequential_one_does(self) -> None:
        # Arrange
        part = ready(BRANCH)

        # Act
        part.step()

        # Assert
        self.assertTrue(part.bus.cycles[1].kind.touches_memory)

    def test_each_type_carries_the_name_table_three_gives_it(self) -> None:
        # Arrange
        part = ready(MULTIPLY_R0_R1_R2)

        # Act
        part.step()

        # Assert
        self.assertEqual(
            [row.kind.name for row in part.bus.cycles[-2:]], ["internal", "sequential"]
        )


class WhatOneRecordedCycleCarriesTest(unittest.TestCase):
    def test_it_carries_the_address_driven_in_that_cycle(self) -> None:
        # Arrange
        part = ready(BRANCH)

        # Act
        part.step()

        # Assert
        self.assertEqual([row.address for row in part.bus.cycles], [0x08, 0x40, 0x44])

    def test_an_opcode_fetch_drives_nopc_low(self) -> None:
        # Arrange
        part = ready(BRANCH)

        # Act
        part.step()

        # Assert
        self.assertEqual({row.nopc for row in part.bus.cycles}, {0})

    def test_a_data_transfer_drives_it_high(self) -> None:
        # Arrange
        part = ready(STORE_R0_TO_R1)

        # Act
        part.step()

        # Assert
        self.assertEqual(data_row(part).nopc, 1)

    def test_a_word_access_drives_nbw_high(self) -> None:
        # Arrange
        part = ready(LOAD_R0_FROM_R1)

        # Act
        part.step()

        # Assert
        self.assertEqual(data_row(part).nbw, 1)

    def test_a_byte_access_drives_it_low(self) -> None:
        # Arrange
        part = ready(LOAD_BYTE_R0_FROM_R1)

        # Act
        part.step()

        # Assert
        self.assertEqual(data_row(part).nbw, 0)

    def test_a_write_drives_nrw_high(self) -> None:
        # Arrange
        part = ready(STORE_R0_TO_R1)

        # Act
        part.step()

        # Assert
        self.assertEqual(data_row(part).nrw, 1)

    def test_and_a_read_drives_it_low(self) -> None:
        # Arrange
        part = ready(LOAD_R0_FROM_R1)

        # Act
        part.step()

        # Assert
        self.assertEqual(data_row(part).nrw, 0)

    def test_the_lock_line_is_low_except_during_a_swap(self) -> None:
        # Arrange
        part = ready(STORE_R0_TO_R1)

        # Act
        part.step()

        # Assert
        self.assertEqual({row.lock for row in part.bus.cycles}, {0})

    def test_and_a_swap_drives_it_high(self) -> None:
        # Arrange
        part = ready(SWAP_R0_R2_AT_R1)

        # Act
        part.step()

        # Assert
        self.assertEqual(
            [row.lock for row in part.bus.cycles if row.address == DATA and row.nopc], [1, 1]
        )

    def test_a_cycle_says_what_it_was_when_printed(self) -> None:
        # Arrange
        part = ready(ANDEQ_R0_R0_R0)

        # Act
        part.step()

        # Assert
        self.assertEqual(repr(part.bus.cycles[0]), "Cycle(S, address=0x00000008, nopc=0)")


class TheForecastIsWhatTableTwentyCountsTest(unittest.TestCase):
    def test_a_branch_costs_two_sequential_and_one_non_sequential(self) -> None:
        # Arrange
        part = ready(BRANCH)

        # Act
        part.step()

        # Assert
        spent = part.spent
        self.assertEqual((spent.s, spent.n, spent.i, spent.c), (2, 1, 0, 0))

    def test_a_store_register_costs_two_non_sequential(self) -> None:
        # Arrange
        part = ready(STORE_R0_TO_R1)

        # Act
        part.step()

        # Assert
        spent = part.spent
        self.assertEqual((spent.s, spent.n, spent.i, spent.c), (0, 2, 0, 0))

    def test_the_longest_multiply_costs_one_sequential_and_sixteen_internal(self) -> None:
        # Arrange
        part = ready(MULTIPLY_R0_R1_R2)

        # Act
        part.step()

        # Assert
        self.assertEqual((part.spent.s, part.spent.i), (1, 16))

    def test_a_part_that_has_run_nothing_reports_nothing(self) -> None:
        # Arrange
        part = Cpu("arm60", fill=0)

        # Act
        spent = part.spent

        # Assert
        self.assertEqual((spent.total, part.bus.cycles), (0, []))

    def test_the_bus_hands_back_one_row_per_cycle_spent(self) -> None:
        # Arrange
        part = ready(BRANCH)

        # Act
        spent = part.step()

        # Assert
        self.assertEqual(len(part.bus.cycles), spent)

    def test_each_instruction_starts_with_an_empty_record(self) -> None:
        # Arrange
        part = ready(ANDEQ_R0_R0_R0)

        # Act
        part.step()

        # Assert
        self.assertEqual(len(part.bus.cycles), 1)


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_a_cycle_refuses_a_name_it_does_not_have(self) -> None:
        # Arrange
        part = ready(ANDEQ_R0_R0_R0)
        part.step()
        row = part.bus.cycles[0]

        # Act
        with self.assertRaises(AttributeError) as caught:
            row.q = 1  # type: ignore[attr-defined]

        # Assert
        self.assertIn("q", str(caught.exception))

    def test_the_bus_refuses_one_too(self) -> None:
        # Arrange
        bus = Cpu("arm60").bus

        # Act
        with self.assertRaises(AttributeError) as caught:
            bus.q = 1  # type: ignore[attr-defined]

        # Assert
        self.assertIn("q", str(caught.exception))

    def test_a_type_refuses_any_write_at_all(self) -> None:
        # Arrange
        kind = kind_of(BRANCH, 1)

        # Act
        with self.assertRaises(AttributeError) as caught:
            kind.letter = "N"

        # Assert
        self.assertIn("Table 3", str(caught.exception))


class ACycleTypeNamesItselfTest(unittest.TestCase):
    def test_a_type_says_which_letter_it_is_when_printed(self) -> None:
        # Arrange
        kind = kind_of(BRANCH, 1)

        # Act
        shown = repr(kind)

        # Assert
        self.assertEqual(shown, "CycleType(S)")

    def test_and_each_type_prints_a_different_letter(self) -> None:
        # Arrange
        kinds = (kind_of(BRANCH, 0), kind_of(BRANCH, 1), kind_of(MULTIPLY_R0_R1_R2, 0))

        # Act
        shown = [repr(one) for one in kinds]

        # Assert
        self.assertEqual(shown, ["CycleType(N)", "CycleType(S)", "CycleType(I)"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

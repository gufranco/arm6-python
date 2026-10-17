from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import (  # noqa: E402
    Cpu,
    EmptyRegisterList,
    Memory,
    RunLimit,
    UnknownModelError,
    UnspecifiedEncoding,
)
from conformance.printed import quote, value  # noqa: E402

MOV_R0_R1 = 0xE1A00001
MOV_PC_R0 = 0xE1A0F000
BRANCH = 0xEA000000
BRANCH_WITH_LINK = 0xEB000000
LOAD_R0_FROM_R1 = 0xE5910000
STORE_R0_TO_R1 = 0xE5810000
LOAD_MANY = 0xE891000D
STORE_MANY = 0xE881000D
SWAP_WORD = 0xE1020091
SOFTWARE_INTERRUPT = 0xEF000000
MULTIPLY = 0xE0000291
UNDEFINED = 0xE6000010
NEVER = 0xFA000000
COPROCESSOR_OPERATION = 0xEE012103
LONG_MULTIPLY = 0xE0812394
I_BIT = 7
F_BIT = 6


def machine(*words: int) -> Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


def bit(cpu: Cpu, place: int) -> bool:
    return bool(cpu.registers.cpsr >> place & 1)


class BuiltTheWayTheFamilyBuildsThemTest(unittest.TestCase):
    def test_a_part_is_built_by_naming_a_model(self) -> None:
        held = Cpu("arm60")

        self.assertEqual(held.model.name, "arm60")

    def test_a_name_no_model_goes_by_is_refused(self) -> None:
        with self.assertRaises(UnknownModelError):
            Cpu("arm7tdmi")

    def test_a_store_the_caller_supplies_is_the_one_the_part_uses(self) -> None:
        store = Memory(fill=0)

        held = Cpu("arm60", store)

        self.assertIs(held.memory, store)

    def test_and_one_is_built_when_the_argument_is_left_out(self) -> None:
        held = Cpu("arm60")

        self.assertIsInstance(held.memory, Memory)

    def test_a_part_says_what_it_is_when_printed(self) -> None:
        held = repr(Cpu("arm60"))

        self.assertEqual(held, "Cpu('arm60')")

    def test_nothing_starts_cleared(self) -> None:
        held = Cpu("arm60", seed=11)

        values = {held.registers.read(one) for one in range(15)}

        self.assertNotEqual(values, {0})

    def test_the_counter_starts_holding_rubbish_too(self) -> None:
        held = Cpu("arm60", seed=11)

        self.assertNotEqual(held.registers.pc, 0)


class ResetDefinesAndPowerOnScramblesTest(unittest.TestCase):
    def test_a_reset_hands_the_part_back_so_the_call_chains(self) -> None:
        held = Cpu("arm60", fill=0)

        back = held.reset()

        self.assertIs(back, held)

    def test_it_fetches_the_next_instruction_from_address_zero(self) -> None:
        held = Cpu("arm60", fill=0)

        held.reset()

        self.assertEqual(held.registers.pc, 0)

    def test_it_forces_supervisor_mode(self) -> None:
        # Arrange
        held = Cpu("arm60", fill=0)

        # Act
        held.reset()

        # Assert
        self.assertEqual(held.mode.name, "svc32", quote("resetForcesMode"))

    def test_it_sets_both_interrupt_disables(self) -> None:
        # Arrange
        held = Cpu("arm60", fill=0)

        # Act
        held.reset()

        # Assert
        disabled = (bit(held, I_BIT), bit(held, F_BIT))
        self.assertEqual(disabled, (True, True), quote("resetForcesMode"))

    def test_the_saved_counter_it_writes_is_not_defined_so_it_is_not_zero(self) -> None:
        # Arrange
        held = Cpu("arm60", fill=0)

        # Act
        held.reset()

        # Assert
        self.assertNotEqual(
            held.registers.read(14), 0, (quote("resetOverwrites"), quote("resetUndefined"))
        )

    def test_and_neither_is_the_saved_status_register(self) -> None:
        # Arrange
        held = Cpu("arm60", fill=0)

        # Act
        held.reset()

        # Assert
        self.assertNotEqual(
            held.registers.saved(), 0, (quote("resetOverwrites"), quote("resetUndefined"))
        )

    def test_a_reset_costs_at_least_two_cycles_of_dummy_fetches(self) -> None:
        held = Cpu("arm60", fill=0)

        held.reset()

        self.assertGreaterEqual(held.spent.total, 5)

    def test_those_dummy_fetches_have_an_incrementing_address(self) -> None:
        held = Cpu("arm60", fill=0)
        held.registers.pc = 0x1000

        held.reset()

        self.assertEqual([one.address for one in held.bus.cycles[:2]], [0x1000, 0x1004])

    def test_a_board_that_holds_the_line_longer_pays_for_it(self) -> None:
        held = Cpu("arm60", fill=0)

        held.reset(low_cycles=6)

        self.assertEqual(held.spent.total, 9)

    def test_a_board_cannot_ask_for_less_than_the_datasheet_states(self) -> None:
        held = Cpu("arm60", fill=0)

        held.reset(low_cycles=0)

        self.assertEqual(held.spent.total, 5)

    def test_the_clock_the_board_runs_on_is_not_rewound_by_a_reset(self) -> None:
        held = machine(MOV_R0_R1)
        held.run_for(1)
        before = held.cycles

        held.reset()

        self.assertGreater(held.cycles, before)

    def test_but_the_instruction_count_starts_again(self) -> None:
        held = machine(MOV_R0_R1)
        held.run_for(1)

        held.reset()

        self.assertEqual(held.steps, 0)


class WhatTableTwentySaysEachFormCostsTest(unittest.TestCase):
    def test_a_data_operation_costs_one_sequential_cycle(self) -> None:
        held = machine(MOV_R0_R1)

        spent = held.step()

        self.assertEqual((spent, held.spent.s), (1, 1))

    def test_a_data_operation_writing_the_counter_costs_two_sequential_and_one_not(
        self,
    ) -> None:
        held = machine(MOV_PC_R0)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 1, 0))

    def test_a_branch_costs_two_sequential_and_one_non_sequential(self) -> None:
        held = machine(BRANCH)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 1, 0))

    def test_a_load_costs_one_of_each(self) -> None:
        held = machine(LOAD_R0_FROM_R1)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (1, 1, 1))

    def test_a_store_costs_two_non_sequential_cycles_and_nothing_else(self) -> None:
        held = machine(STORE_R0_TO_R1)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (0, 2, 0))

    def test_a_load_of_three_registers_costs_three_sequential_one_of_each_other(
        self,
    ) -> None:
        held = machine(LOAD_MANY)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (3, 1, 1))

    def test_a_store_of_three_registers_costs_two_sequential_and_two_non_sequential(
        self,
    ) -> None:
        held = machine(STORE_MANY)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 2, 0))

    def test_a_swap_costs_one_sequential_two_non_sequential_and_one_internal(self) -> None:
        held = machine(SWAP_WORD)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (1, 2, 1))

    def test_a_software_interrupt_costs_two_sequential_and_one_non_sequential(self) -> None:
        held = machine(SOFTWARE_INTERRUPT)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 1, 0))

    def test_the_shortest_multiply_costs_one_sequential_and_one_internal(self) -> None:
        held = machine(MULTIPLY)

        held.step()

        self.assertEqual((held.spent.s, held.spent.i), (1, 1))

    def test_a_longer_multiply_costs_one_internal_cycle_per_booth_band(self) -> None:
        held = machine(MULTIPLY)
        held.registers.write(2, 0x100)

        held.step()

        self.assertEqual((held.spent.s, held.spent.i), (1, 5))

    def test_the_longest_multiply_costs_sixteen_internal_cycles(self) -> None:
        # Arrange
        held = machine(MULTIPLY)
        held.registers.write(2, 0xFFFFFFFF)

        # Act
        held.step()

        # Assert
        self.assertEqual(f"{held.spent.s}S+{held.spent.i}I", value("multiplyWorstCase"))

    def test_an_instruction_whose_condition_fails_costs_one_sequential_cycle(self) -> None:
        # Arrange
        held = machine(NEVER)

        # Act
        spent = held.step()

        # Assert
        self.assertEqual((spent, held.spent.s), (1, 1), quote("conditionNotMet"))

    def test_an_undefined_instruction_costs_one_cycle_more_than_the_trap(self) -> None:
        held = machine(UNDEFINED)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 1, 1))

    def test_a_coprocessor_instruction_with_none_attached_costs_the_same(self) -> None:
        held = machine(COPROCESSOR_OPERATION)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 1, 1))


class WhatEachInstructionActuallyDidTest(unittest.TestCase):
    def test_a_move_copies_one_register_to_another(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.write(1, 0x1234)

        held.step()

        self.assertEqual(held.registers.read(0), 0x1234)

    def test_a_branch_with_link_leaves_the_following_address_behind(self) -> None:
        held = machine(BRANCH_WITH_LINK)

        held.step()

        self.assertEqual(held.registers.read(14), 4)

    def test_a_load_brings_back_what_was_written(self) -> None:
        held = machine(LOAD_R0_FROM_R1)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2000, 0xCAFEBABE)

        held.step()

        self.assertEqual(held.registers.read(0), 0xCAFEBABE)

    def test_an_unaligned_load_rotates_rather_than_faulting(self) -> None:
        held = machine(LOAD_R0_FROM_R1)
        held.registers.write(1, 0x2001)
        held.memory.write_word(0x2000, 0x11223344)

        held.step()

        self.assertEqual(held.registers.read(0), 0x44112233)

    def test_a_store_of_the_counter_writes_the_address_plus_twelve(self) -> None:
        # Arrange
        held = machine(0xE581F000)
        held.registers.write(1, 0x2000)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.memory.read_word(0x2000), value("storedCounter"))

    def test_a_block_load_takes_the_lowest_register_from_the_lowest_address(self) -> None:
        # Arrange
        held = machine(LOAD_MANY)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2000, 0xA)
        held.memory.write_word(0x2004, 0xB)
        held.memory.write_word(0x2008, 0xC)

        # Act
        held.step()

        # Assert
        self.assertEqual(
            (held.registers.read(0), held.registers.read(2), held.registers.read(3)),
            (0xA, 0xB, 0xC),
            quote("blockTransferOrder"),
        )

    def test_a_swap_exchanges_the_register_and_the_memory(self) -> None:
        held = machine(SWAP_WORD)
        held.registers.write(2, 0x2000)
        held.registers.write(1, 0x1111)
        held.memory.write_word(0x2000, 0x2222)

        held.step()

        self.assertEqual((held.registers.read(0), held.memory.read_word(0x2000)), (0x2222, 0x1111))

    def test_a_multiply_produces_the_product(self) -> None:
        held = machine(MULTIPLY)
        held.registers.write(1, 6)
        held.registers.write(2, 7)

        held.step()

        self.assertEqual(held.registers.read(0), 42)

    def test_a_multiply_whose_destination_is_its_multiplicand_gives_zero(self) -> None:
        # Arrange
        held = machine(0xE0010291)
        held.registers.write(1, 6)
        held.registers.write(2, 7)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(1), 0, quote("multiplyRdEqualsRm"))

    def test_an_empty_register_list_is_refused_rather_than_guessed_at(self) -> None:
        # Arrange
        held = machine(0xE8910000)

        # Act
        with self.assertRaises(EmptyRegisterList, msg=quote("emptyRegisterList")):
            held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0)

    def test_an_encoding_outside_the_figure_is_refused_too(self) -> None:
        held = machine(LONG_MULTIPLY)

        with self.assertRaises(UnspecifiedEncoding):
            held.step()

    def test_and_the_refusal_names_the_word_it_could_not_answer_for(self) -> None:
        held = machine(LONG_MULTIPLY)

        with self.assertRaises(UnspecifiedEncoding) as caught:
            held.step()

        self.assertIn("E0812394", str(caught.exception))


class DrivenByAClockTest(unittest.TestCase):
    def test_a_budget_reports_what_it_really_spent(self) -> None:
        held = machine(*([MOV_R0_R1] * 40))

        spent = held.run_for(16)

        self.assertGreaterEqual(spent, 16)

    def test_a_budget_overshoots_rather_than_splitting_an_instruction(self) -> None:
        held = machine(BRANCH_WITH_LINK, *([MOV_R0_R1] * 8))

        spent = held.run_for(1)

        self.assertEqual(spent, 3)

    def test_the_tally_is_cumulative_across_instructions(self) -> None:
        held = machine(*([MOV_R0_R1] * 8))

        held.run_for(4)

        self.assertEqual(held.cycles, held.tally.total)

    def test_a_bounded_run_gives_up_rather_than_hanging(self) -> None:
        held = machine(*([MOV_R0_R1] * 64))

        with self.assertRaises(RunLimit):
            held.run_until(lambda _: False, limit=8)

    def test_and_stops_when_the_predicate_holds(self) -> None:
        held = machine(*([MOV_R0_R1] * 64))

        back = held.run_until(lambda one: one.registers.pc >= 8, limit=8)

        self.assertIs(back, held)

    def test_a_watcher_is_called_once_per_cycle(self) -> None:
        held = machine(BRANCH)
        seen = []
        held.on_cycle = lambda one: seen.append(one.cycles)

        held.step()

        self.assertEqual(len(seen), 3)

    def test_a_part_is_never_held_because_nothing_stops_it(self) -> None:
        held = machine(MOV_R0_R1)

        self.assertFalse(held.held())


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_part_refuses_a_name_it_does_not_have(self) -> None:
        held = Cpu("arm60")

        with self.assertRaises(AttributeError):
            held.q = 1  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main(verbosity=2)

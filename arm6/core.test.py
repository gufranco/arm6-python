"""That a whole part behaves, and costs, what chapter 10 and Table 20 say.

The cycle counts here are the point of the file. A model can spend the right
number of cycles driving the wrong addresses, so the bus record is checked as
well as the total, and every figure is the one Table 20 prints for that form.

One of them is not. Table 5 gives a data operation with a register-specified
shift two rows whose pins are byte for byte identical to the first two rows of
Table 6's shortest multiply, which Table 20 costs at `1S+1I`. Table 20 costs the
data operation at `1S+1S`. The two cannot both be right, the per-cycle table is
the finer statement, and the divergence is recorded rather than resolved by
preference.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import psr  # noqa: E402
from arm6.core import Cpu  # noqa: E402
from arm6.errors import RunLimit, UnknownModelError  # noqa: E402
from arm6.memory import Memory  # noqa: E402
from arm6.transfers import EmptyRegisterList, UnspecifiedEncoding  # noqa: E402

MOV_R0_R1 = 0xE1A00001
MOV_R0_R1_LSL_R2 = 0xE1A00211
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


def machine(*words: int, **options: object) -> Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0), fill=0, **options)  # type: ignore[arg-type]
    held.registers.pc = 0
    return held


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
        held = Cpu("arm60", fill=0)

        held.reset()

        self.assertEqual(held.mode.name, "svc32")

    def test_it_sets_both_interrupt_disables(self) -> None:
        held = Cpu("arm60", fill=0)

        held.reset()

        disabled = (
            psr.flag(held.registers.cpsr, psr.I_BIT),
            psr.flag(held.registers.cpsr, psr.F_BIT),
        )
        self.assertEqual(disabled, (True, True))

    def test_the_saved_counter_it_writes_is_not_defined_so_it_is_not_zero(self) -> None:
        held = Cpu("arm60", fill=0)

        held.reset()

        self.assertNotEqual(held.registers.read(14), 0)

    def test_and_neither_is_the_saved_status_register(self) -> None:
        held = Cpu("arm60", fill=0)

        held.reset()

        self.assertNotEqual(held.registers.spsr["svc"], 0)

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
        held = machine(MULTIPLY)
        held.registers.write(2, 0xFFFFFFFF)

        held.step()

        self.assertEqual((held.spent.s, held.spent.i), (1, 16))

    def test_an_instruction_whose_condition_fails_costs_one_sequential_cycle(self) -> None:
        held = machine(NEVER)

        spent = held.step()

        self.assertEqual((spent, held.spent.s), (1, 1))

    def test_an_undefined_instruction_costs_one_cycle_more_than_the_trap(self) -> None:
        held = machine(UNDEFINED)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 1, 1))

    def test_a_coprocessor_instruction_with_none_attached_costs_the_same(self) -> None:
        held = machine(COPROCESSOR_OPERATION)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 1, 1))


class TheRegisterShiftCycleTheTablesDisagreeAboutTest(unittest.TestCase):
    def test_the_per_cycle_table_makes_the_extra_cycle_internal(self) -> None:
        held = machine(MOV_R0_R1_LSL_R2)

        held.step()

        self.assertEqual((held.spent.s, held.spent.i), (1, 1))

    def test_which_is_the_shape_the_shortest_multiply_has(self) -> None:
        shifted = machine(MOV_R0_R1_LSL_R2)
        multiplied = machine(MULTIPLY)

        shifted.step()
        multiplied.step()

        self.assertEqual(
            [one.kind.letter for one in shifted.bus.cycles],
            [one.kind.letter for one in multiplied.bus.cycles],
        )


class WhatTheBusActuallyDroveTest(unittest.TestCase):
    def test_a_branch_drives_the_prefetch_then_the_destination_then_the_next(self) -> None:
        held = machine(BRANCH)

        held.step()

        self.assertEqual([one.address for one in held.bus.cycles], [8, 8, 12])

    def test_a_store_drives_the_address_it_computed_with_the_write_line_high(self) -> None:
        held = machine(STORE_R0_TO_R1)
        held.registers.write(1, 0x2000)
        held.registers.write(0, 0xDEADBEEF)

        held.step()

        self.assertEqual((held.bus.cycles[1].address, held.bus.cycles[1].nrw), (0x2000, 1))

    def test_a_byte_access_drives_the_width_line_low(self) -> None:
        held = machine(0xE5C10000)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.bus.cycles[1].nbw, 0)

    def test_a_swap_holds_the_lock_line_high_across_both_of_its_accesses(self) -> None:
        held = machine(SWAP_WORD)
        held.registers.write(2, 0x2000)

        held.step()

        self.assertEqual([one.lock for one in held.bus.cycles], [0, 1, 1, 0])

    def test_an_instruction_fetch_drives_the_opcode_line_low(self) -> None:
        held = machine(MOV_R0_R1)

        held.step()

        self.assertEqual(held.bus.cycles[0].nopc, 0)

    def test_a_privileged_mode_drives_the_translate_line_high(self) -> None:
        held = machine(MOV_R0_R1)

        held.step()

        self.assertEqual(held.bus.cycles[0].ntrans, 1)

    def test_and_a_user_mode_drives_it_low(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])

        held.step()

        self.assertEqual(held.bus.cycles[0].ntrans, 0)

    def test_a_discarded_prefetch_is_still_a_real_read(self) -> None:
        held = machine(BRANCH, 0, 0x12345678)

        held.step()

        self.assertEqual(held.bus.cycles[0].data, 0x12345678)


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
        held = machine(0xE581F000)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.memory.read_word(0x2000), 12)

    def test_a_block_load_takes_the_lowest_register_from_the_lowest_address(self) -> None:
        held = machine(LOAD_MANY)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2000, 0xA)
        held.memory.write_word(0x2004, 0xB)
        held.memory.write_word(0x2008, 0xC)

        held.step()

        self.assertEqual(
            (held.registers.read(0), held.registers.read(2), held.registers.read(3)),
            (0xA, 0xB, 0xC),
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
        held = machine(0xE0010291)
        held.registers.write(1, 6)
        held.registers.write(2, 7)

        held.step()

        self.assertEqual(held.registers.read(1), 0)

    def test_an_empty_register_list_is_refused_rather_than_guessed_at(self) -> None:
        held = machine(0xE8910000)

        with self.assertRaises(EmptyRegisterList):
            held.step()

    def test_an_encoding_outside_the_figure_is_refused_too(self) -> None:
        held = machine(LONG_MULTIPLY)

        with self.assertRaises(UnspecifiedEncoding):
            held.step()

    def test_and_the_refusal_names_the_word_it_could_not_answer_for(self) -> None:
        held = machine(LONG_MULTIPLY)

        with self.assertRaises(UnspecifiedEncoding) as caught:
            held.step()

        self.assertIn("E0812394", str(caught.exception))


class WhereAnExceptionGoesTest(unittest.TestCase):
    def test_a_software_interrupt_vectors_to_eight(self) -> None:
        held = machine(SOFTWARE_INTERRUPT)

        held.step()

        self.assertEqual(held.registers.pc, 0x08)

    def test_and_enters_supervisor_mode(self) -> None:
        held = machine(SOFTWARE_INTERRUPT)

        held.step()

        self.assertEqual(held.mode.name, "svc32")

    def test_and_leaves_the_return_address_in_the_link_register(self) -> None:
        held = machine(SOFTWARE_INTERRUPT)

        held.step()

        self.assertEqual(held.registers.read(14), 4)

    def test_and_banks_the_status_it_came_in_with(self) -> None:
        held = machine(SOFTWARE_INTERRUPT)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.Z_BIT, True)
        before = held.registers.cpsr

        held.step()

        self.assertEqual(held.registers.spsr["svc"], before)

    def test_an_undefined_instruction_vectors_to_four(self) -> None:
        held = machine(UNDEFINED)

        held.step()

        self.assertEqual(held.registers.pc, 0x04)

    def test_and_enters_the_undefined_mode(self) -> None:
        held = machine(UNDEFINED)

        held.step()

        self.assertEqual(held.mode.name, "und32")

    def test_every_vector_the_datasheet_lists_is_here(self) -> None:
        from arm6.core import VECTORS

        self.assertEqual(
            sorted(VECTORS.values()),
            [0x00, 0x04, 0x08, 0x0C, 0x10, 0x18, 0x1C],
        )

    def test_the_address_exception_vector_is_not_among_them(self) -> None:
        from arm6.core import VECTORS

        self.assertNotIn(0x14, VECTORS.values())


class TheTwoInterruptLinesTest(unittest.TestCase):
    def test_a_request_on_the_lower_line_is_taken_when_it_is_not_masked(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.I_BIT, False)

        taken = held.irq()

        self.assertTrue(taken)

    def test_and_is_refused_when_it_is(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.I_BIT, True)

        taken = held.irq()

        self.assertFalse(taken)

    def test_a_request_on_the_higher_line_is_masked_by_its_own_bit(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.F_BIT, True)

        taken = held.fiq()

        self.assertFalse(taken)

    def test_a_line_that_is_taken_vectors_on_the_next_instruction(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.I_BIT, False)
        held.irq()

        held.step()

        self.assertEqual(held.registers.pc, 0x18)

    def test_the_higher_line_wins_when_both_are_offered(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.I_BIT, False)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.F_BIT, False)
        held.irq()
        held.fiq()

        held.step()

        self.assertEqual(held.registers.pc, 0x1C)

    def test_taking_the_higher_line_masks_both(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.F_BIT, False)
        held.fiq()

        held.step()

        self.assertEqual(
            (
                psr.flag(held.registers.cpsr, psr.I_BIT),
                psr.flag(held.registers.cpsr, psr.F_BIT),
            ),
            (True, True),
        )

    def test_a_request_withdrawn_before_the_part_looks_is_not_taken(self) -> None:
        held = machine(MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.I_BIT, False)
        held.irq()
        held.irq(level=False)

        held.step()

        self.assertEqual(held.registers.pc, 4)

    def test_a_masked_request_stays_on_the_line_until_it_is_unmasked(self) -> None:
        held = machine(MOV_R0_R1, MOV_R0_R1)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.I_BIT, True)
        held.irq()
        held.step()
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.I_BIT, False)

        held.step()

        self.assertEqual(held.registers.pc, 0x18)


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


class TheConditionFieldDecidesTest(unittest.TestCase):
    def test_an_instruction_whose_condition_holds_executes(self) -> None:
        held = machine(0x01A00001)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.Z_BIT, True)
        held.registers.write(1, 0x99)

        held.step()

        self.assertEqual(held.registers.read(0), 0x99)

    def test_and_one_whose_condition_fails_does_not(self) -> None:
        held = machine(0x01A00001)
        held.registers.cpsr = psr.with_flag(held.registers.cpsr, psr.Z_BIT, False)
        held.registers.write(1, 0x99)
        held.registers.write(0, 0x11)

        held.step()

        self.assertEqual(held.registers.read(0), 0x11)

    def test_every_condition_code_is_reachable(self) -> None:
        held = machine(MOV_R0_R1)

        answers = {held.passes(code << 28) for code in range(16)}

        self.assertEqual(answers, {True, False})

    def test_the_never_code_never_executes(self) -> None:
        held = machine(MOV_R0_R1)

        self.assertFalse(held.passes(0xF0000000))

    def test_the_always_code_always_does(self) -> None:
        held = machine(MOV_R0_R1)

        self.assertTrue(held.passes(0xE0000000))


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_part_refuses_a_name_it_does_not_have(self) -> None:
        held = Cpu("arm60")

        with self.assertRaises(AttributeError):
            held.q = 1  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main(verbosity=2)

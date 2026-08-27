"""That the pieces the transfer instructions are built from match the pages.

The instructions themselves are checked against the cycle tables in
`conformance/`, where a whole part can be driven. What is checked here is the
arithmetic underneath them: the sign extension a branch offset gets, the order a
register list is transferred in, and the rotation an unaligned word load applies,
all of which are stated in the datasheet and none of which needs a part to test.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import psr, transfers  # noqa: E402
from arm6.core import Cpu  # noqa: E402
from arm6.memory import Memory  # noqa: E402


class TheBranchOffsetTest(unittest.TestCase):
    def test_a_forward_branch_lands_past_the_prefetch(self) -> None:
        held = transfers.branch_target(0x1000, 0xEA000000)

        self.assertEqual(held, 0x1008)

    def test_the_offset_is_shifted_left_two_bits(self) -> None:
        held = transfers.branch_target(0x1000, 0xEA000001)

        self.assertEqual(held, 0x100C)

    def test_a_backward_branch_sign_extends_the_offset(self) -> None:
        held = transfers.branch_target(0x1000, 0xEAFFFFFF)

        self.assertEqual(held, 0x1004)

    def test_the_furthest_branch_back_is_thirty_two_megabytes(self) -> None:
        held = transfers.branch_target(0x4000000, 0xEA800000)

        self.assertEqual(held, 0x2000008)

    def test_the_furthest_branch_forward_is_thirty_two_megabytes(self) -> None:
        held = transfers.branch_target(0, 0xEA7FFFFF)

        self.assertEqual(held, 0x01FFFFFC + 8)

    def test_a_target_past_the_top_of_the_bus_wraps(self) -> None:
        held = transfers.branch_target(0xFFFFFFF0, 0xEA000010)

        self.assertEqual(held, 0x00000038)


class TheRegisterListTest(unittest.TestCase):
    def test_the_lowest_register_comes_first(self) -> None:
        held = transfers.registers_in(0b0000_0000_0000_1011)

        self.assertEqual(held, (0, 1, 3))

    def test_the_counter_is_always_last_when_it_is_in_the_list(self) -> None:
        held = transfers.registers_in(0b1000_0000_0000_0001)

        self.assertEqual(held, (0, 15))

    def test_every_register_can_be_named_at_once(self) -> None:
        held = transfers.registers_in(0xFFFF)

        self.assertEqual(held, tuple(range(16)))

    def test_an_empty_list_names_nothing(self) -> None:
        held = transfers.registers_in(0)

        self.assertEqual(held, ())

    def test_the_number_transferred_is_the_number_named(self) -> None:
        held = len(transfers.registers_in(0b0101_0101_0101_0101))

        self.assertEqual(held, 8)


class TheUnalignedWordLoadTest(unittest.TestCase):
    def test_an_aligned_load_is_not_rotated(self) -> None:
        held = transfers.rotate_load(0x11223344, 0x1000)

        self.assertEqual(held, 0x11223344)

    def test_a_load_from_the_second_byte_puts_it_at_the_bottom(self) -> None:
        held = transfers.rotate_load(0x11223344, 0x1001)

        self.assertEqual(held, 0x44112233)

    def test_a_load_from_the_third_byte_rotates_by_two_bytes(self) -> None:
        held = transfers.rotate_load(0x11223344, 0x1002)

        self.assertEqual(held, 0x33441122)

    def test_a_load_from_the_fourth_byte_rotates_by_three(self) -> None:
        held = transfers.rotate_load(0x11223344, 0x1003)

        self.assertEqual(held, 0x22334411)

    def test_the_addressed_byte_always_ends_up_in_the_bottom_eight_bits(self) -> None:
        held = {transfers.rotate_load(0x11223344, 0x1000 + one) & 0xFF for one in range(4)}

        self.assertEqual(held, {0x44, 0x33, 0x22, 0x11})


class TheTransferAddressTest(unittest.TestCase):
    def test_an_offset_up_is_added_to_the_base(self) -> None:
        held = transfers.offset_address(0x1000, 0x20, up=True)

        self.assertEqual(held, 0x1020)

    def test_an_offset_down_is_subtracted(self) -> None:
        held = transfers.offset_address(0x1000, 0x20, up=False)

        self.assertEqual(held, 0x0FE0)

    def test_an_address_that_leaves_the_bus_wraps(self) -> None:
        held = transfers.offset_address(0xFFFFFFF0, 0x20, up=True)

        self.assertEqual(held, 0x00000010)

    def test_and_one_that_goes_below_zero_wraps_too(self) -> None:
        held = transfers.offset_address(0x10, 0x20, up=False)

        self.assertEqual(held, 0xFFFFFFF0)


class WhatARegisterStoreOfTheCounterHoldsTest(unittest.TestCase):
    def test_the_stored_value_is_the_instruction_address_plus_twelve(self) -> None:
        held = transfers.stored_counter(0x2000)

        self.assertEqual(held, 0x200C)


class DrivenAsWholeInstructionsTest(unittest.TestCase):
    """The transfer forms whose behaviour needs a whole part to show.

    A register offset, a byte access, a load into the counter, a block transfer
    through the user bank and a coprocessor instruction with nothing attached all
    reach past the arithmetic above.
    """

    def part(self, *words: int) -> Cpu:
        image = b"".join(one.to_bytes(4, "little") for one in words)
        held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
        held.registers.pc = 0
        return held

    def test_a_register_offset_is_added_to_the_base(self) -> None:
        held = self.part(0xE7910002)
        held.registers.write(1, 0x2000)
        held.registers.write(2, 0x10)
        held.memory.write_word(0x2010, 0xABCD)

        held.step()

        self.assertEqual(held.registers.read(0), 0xABCD)

    def test_a_shifted_register_offset_is_shifted_first(self) -> None:
        held = self.part(0xE7910102)
        held.registers.write(1, 0x2000)
        held.registers.write(2, 0x8)
        held.memory.write_word(0x2020, 0x1234)

        held.step()

        self.assertEqual(held.registers.read(0), 0x1234)

    def test_a_byte_load_brings_back_one_byte(self) -> None:
        held = self.part(0xE5D10000)
        held.registers.write(1, 0x2001)
        held.memory.write_word(0x2000, 0x11223344)

        held.step()

        self.assertEqual(held.registers.read(0), 0x33)

    def test_a_byte_store_writes_one_byte(self) -> None:
        held = self.part(0xE5C10000)
        held.registers.write(1, 0x2000)
        held.registers.write(0, 0xAABBCCDD)

        held.step()

        self.assertEqual(held.memory.read_word(0x2000), 0xDD)

    def test_a_post_indexed_transfer_writes_the_base_back(self) -> None:
        held = self.part(0xE4910004)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.registers.read(1), 0x2004)

    def test_a_pre_indexed_transfer_writes_it_back_only_when_asked(self) -> None:
        held = self.part(0xE5B10004)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.registers.read(1), 0x2004)

    def test_an_offset_downwards_subtracts(self) -> None:
        held = self.part(0xE5110004)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x1FFC, 0x999)

        held.step()

        self.assertEqual(held.registers.read(0), 0x999)

    def test_a_load_into_the_counter_refills_the_pipeline(self) -> None:
        held = self.part(0xE591F000)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2000, 0x40)

        held.step()

        self.assertEqual(held.registers.pc, 0x40)

    def test_and_costs_the_two_extra_cycles_table_twenty_names(self) -> None:
        held = self.part(0xE591F000)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual((held.spent.s, held.spent.n, held.spent.i), (2, 2, 1))

    def test_a_block_load_of_the_counter_refills_the_pipeline_too(self) -> None:
        held = self.part(0xE8918001)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2000, 0x11)
        held.memory.write_word(0x2004, 0x40)

        held.step()

        self.assertEqual((held.registers.read(0), held.registers.pc), (0x11, 0x40))

    def test_a_block_transfer_that_writes_the_base_back_does_so(self) -> None:
        held = self.part(0xE8B1000C)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.registers.read(1), 0x2008)

    def test_a_block_load_that_names_its_own_base_takes_the_loaded_value(self) -> None:
        held = self.part(0xE8B10003)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2004, 0xC0FFEE)

        held.step()

        self.assertEqual(held.registers.read(1), 0xC0FFEE)

    def test_a_block_store_puts_the_unchanged_base_out_when_it_is_first(self) -> None:
        held = self.part(0xE8A00003)
        held.registers.write(0, 0x2000)
        held.registers.write(1, 0xAA)

        held.step()

        self.assertEqual(held.memory.read_word(0x2000), 0x2000)

    def test_and_the_modified_base_when_it_is_second_or_later(self) -> None:
        held = self.part(0xE8A20006)
        held.registers.write(2, 0x2000)
        held.registers.write(1, 0xAA)

        held.step()

        self.assertEqual(held.memory.read_word(0x2004), 0x2008)

    def test_a_block_transfer_downwards_starts_below_the_base(self) -> None:
        held = self.part(0xE9110003)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x1FF8, 0xAA)
        held.memory.write_word(0x1FFC, 0xBB)

        held.step()

        self.assertEqual((held.registers.read(0), held.registers.read(1)), (0xAA, 0xBB))

    def test_a_block_store_writes_every_register_it_names(self) -> None:
        held = self.part(0xE8810005)
        held.registers.write(1, 0x2000)
        held.registers.write(0, 0xAA)
        held.registers.write(2, 0xCC)

        held.step()

        self.assertEqual(
            (held.memory.read_word(0x2000), held.memory.read_word(0x2004)), (0xAA, 0xCC)
        )

    def test_a_block_store_of_the_counter_writes_the_address_plus_twelve(self) -> None:
        held = self.part(0xE8818000)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.memory.read_word(0x2000), 12)

    def test_a_block_store_through_the_user_bank_takes_the_user_registers(self) -> None:
        held = self.part(0xE8C12000)
        held.registers.write(1, 0x2000)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])
        held.registers.write(13, 0xDEAD)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["svc32"])
        held.registers.write(13, 0xBEEF)

        held.step()

        self.assertEqual(held.memory.read_word(0x2000), 0xDEAD)

    def test_a_block_load_through_the_user_bank_writes_the_user_registers(self) -> None:
        held = self.part(0xE8D12000)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2000, 0xC0DE)

        held.step()

        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])
        self.assertEqual(held.registers.read(13), 0xC0DE)

    def test_a_block_load_of_the_counter_with_the_flag_restores_the_saved_status(self) -> None:
        held = self.part(0xE8D18000)
        held.registers.write(1, 0x2000)
        held.registers.spsr["svc"] = 0xF00000D3
        held.memory.write_word(0x2000, 0x40)

        held.step()

        self.assertEqual(held.registers.cpsr, 0xF00000D3)

    def test_a_byte_swap_exchanges_one_byte(self) -> None:
        held = self.part(0xE1420091)
        held.registers.write(2, 0x2000)
        held.registers.write(1, 0x99)
        held.memory.write_word(0x2000, 0x11223344)

        held.step()

        self.assertEqual((held.registers.read(0), held.memory.read_byte(0x2000)), (0x44, 0x99))

    def test_a_coprocessor_data_transfer_with_none_attached_traps(self) -> None:
        held = self.part(0xED912100)

        held.step()

        self.assertEqual(held.registers.pc, 0x04)

    def test_a_coprocessor_register_transfer_with_none_attached_traps_too(self) -> None:
        held = self.part(0xEE212113)

        held.step()

        self.assertEqual(held.registers.pc, 0x04)

    def test_a_block_load_of_the_counter_in_a_user_mode_has_no_status_to_restore(self) -> None:
        held = self.part(0xE8D18000)
        held.registers.write(1, 0x2000)
        held.registers.cpsr = psr.with_mode(held.registers.cpsr, psr.MODES["usr32"])
        before = held.registers.cpsr
        held.memory.write_word(0x2000, 0x40)

        held.step()

        self.assertEqual((held.registers.pc, held.registers.cpsr), (0x40, before))

    def test_a_pre_indexed_store_without_write_back_leaves_the_base_alone(self) -> None:
        held = self.part(0xE5810004)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.registers.read(1), 0x2000)

    def test_a_post_indexed_store_writes_the_base_back_anyway(self) -> None:
        held = self.part(0xE4810004)
        held.registers.write(1, 0x2000)

        held.step()

        self.assertEqual(held.registers.read(1), 0x2004)


if __name__ == "__main__":
    unittest.main(verbosity=2)

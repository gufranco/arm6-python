from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402
from conformance.printed import quote, value  # noqa: E402

MODE_FIELD = 0b11111

BRANCH = 0xEA000000

LOAD_R0_FROM_R1 = 0xE5910000

UNALIGNED_WORD = 0x11223344


def at(address: int, word: int) -> arm6.Cpu:
    held = arm6.Cpu("arm60", arm6.Memory(fill=0), fill=0)
    held.memory.write_word(address, word)
    held.registers.pc = address
    return held


def in_mode(cpu: arm6.Cpu, name: str) -> None:
    cpu.registers.cpsr = cpu.registers.cpsr & ~MODE_FIELD | arm6.MODES[name].bits


def loading(base: int, word: int = LOAD_R0_FROM_R1) -> arm6.Cpu:
    held = at(0, word)
    held.registers.write(1, base)
    return held


class TheBranchOffsetTest(unittest.TestCase):
    def test_a_forward_branch_lands_past_the_prefetch(self) -> None:
        # Arrange
        cpu = at(0x1000, BRANCH)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x1008, quote("branchPrefetch"))

    def test_the_offset_is_shifted_left_two_bits(self) -> None:
        # Arrange
        cpu = at(0x1000, BRANCH | 1)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x100C, quote("branchOffset"))

    def test_a_backward_branch_sign_extends_the_offset(self) -> None:
        # Arrange
        cpu = at(0x1000, BRANCH | 0xFFFFFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x1004, quote("branchOffset"))

    def test_the_furthest_branch_back_is_thirty_two_megabytes(self) -> None:
        # Arrange
        cpu = at(0x4000000, BRANCH | 0x800000)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x2000008)

    def test_the_furthest_branch_forward_is_thirty_two_megabytes(self) -> None:
        # Arrange
        cpu = at(0, BRANCH | 0x7FFFFF)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x02000004)

    def test_a_target_past_the_top_of_the_bus_wraps(self) -> None:
        # Arrange
        cpu = at(0xFFFFFFF0, BRANCH | 0x10)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.pc, 0x00000038)


class TheRegisterListTest(unittest.TestCase):
    def test_the_lowest_register_comes_first(self) -> None:
        # Arrange
        cpu = at(0, 0xE894000B)
        cpu.registers.write(4, 0x2000)
        for offset, word in enumerate((0xA, 0xB, 0xC)):
            cpu.memory.write_word(0x2000 + offset * 4, word)

        # Act
        cpu.step()

        # Assert
        self.assertEqual([cpu.registers.read(one) for one in (0, 1, 3)], [0xA, 0xB, 0xC])

    def test_the_counter_is_always_last_when_it_is_in_the_list(self) -> None:
        # Arrange
        cpu = loading(0x2000, 0xE8918001)
        cpu.memory.write_word(0x2000, 0x11)
        cpu.memory.write_word(0x2004, 0x40)

        # Act
        cpu.step()

        # Assert
        self.assertEqual((cpu.registers.read(0), cpu.registers.pc), (0x11, 0x40))

    def test_every_register_can_be_named_at_once(self) -> None:
        # Arrange
        cpu = at(0, 0xE880FFFF)
        cpu.registers.write(0, 0x2000)
        for one in range(1, 15):
            cpu.registers.write(one, 0x100 + one)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(
            [cpu.memory.read_word(0x2000 + one * 4) for one in range(16)],
            [0x2000, *(0x100 + one for one in range(1, 15)), 12],
        )

    def test_an_empty_list_names_nothing(self) -> None:
        # Arrange
        cpu = loading(0x2000, 0xE8910000)

        # Act
        with self.assertRaises(arm6.EmptyRegisterList) as refused:
            cpu.step()

        # Assert
        self.assertIn("7.9", str(refused.exception))

    def test_the_number_transferred_is_the_number_named(self) -> None:
        # Arrange
        cpu = loading(0x2000, 0xE8815555)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(len([row for row in cpu.bus.cycles if row.nrw == 1]), 8)


class TheUnalignedWordLoadTest(unittest.TestCase):
    def loaded(self, address: int) -> arm6.Cpu:
        cpu = loading(address)
        cpu.memory.write_word(0x1000, UNALIGNED_WORD)
        return cpu

    def test_an_aligned_load_is_not_rotated(self) -> None:
        # Arrange
        cpu = self.loaded(0x1000)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.read(0), 0x11223344)

    def test_a_load_from_a_later_byte_rotates_that_byte_to_the_bottom(self) -> None:
        # Arrange
        parts = [self.loaded(0x1000 + one) for one in (1, 2, 3)]

        # Act
        spent = [cpu.step() for cpu in parts]

        # Assert
        self.assertEqual(
            ([cpu.registers.read(0) for cpu in parts], spent),
            ([0x44112233, 0x33441122, 0x22334411], [3, 3, 3]),
        )

    def test_the_addressed_byte_always_ends_up_in_the_bottom_eight_bits(self) -> None:
        # Arrange
        parts = [self.loaded(0x1000 + one) for one in range(4)]

        # Act
        spent = [cpu.step() for cpu in parts]

        # Assert
        self.assertEqual(
            ([cpu.registers.read(0) & 0xFF for cpu in parts], spent),
            ([0x44, 0x33, 0x22, 0x11], [3, 3, 3, 3]),
            quote("unalignedLoad"),
        )


class TheTransferAddressTest(unittest.TestCase):
    def marked(self, base: int, word: int, target: int) -> arm6.Cpu:
        cpu = loading(base, word)
        cpu.memory.write_word(target, 0x5EED)
        return cpu

    def test_an_offset_up_is_added_to_the_base(self) -> None:
        # Arrange
        cpu = self.marked(0x1000, 0xE5910020, 0x1020)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.read(0), 0x5EED)

    def test_an_offset_down_is_subtracted(self) -> None:
        # Arrange
        cpu = self.marked(0x1000, 0xE5110020, 0x0FE0)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.registers.read(0), 0x5EED)

    def test_an_address_that_leaves_the_bus_either_way_wraps(self) -> None:
        # Arrange
        parts = [
            self.marked(0xFFFFFFF0, 0xE5910020, 0x00000010),
            self.marked(0x10, 0xE5110020, 0xFFFFFFF0),
        ]

        # Act
        spent = [cpu.step() for cpu in parts]

        # Assert
        self.assertEqual(([cpu.registers.read(0) for cpu in parts], spent), ([0x5EED] * 2, [3, 3]))


class WhatARegisterStoreOfTheCounterHoldsTest(unittest.TestCase):
    def test_the_stored_value_is_the_instruction_address_plus_twelve(self) -> None:
        # Arrange
        cpu = at(0x2000, 0xE581F000)
        cpu.registers.write(1, 0x3000)

        # Act
        cpu.step()

        # Assert
        self.assertEqual(cpu.memory.read_word(0x3000), 0x2000 + value("storedCounter"))


class DrivenAsWholeInstructionsTest(unittest.TestCase):
    def part(self, *words: int) -> arm6.Cpu:
        image = b"".join(one.to_bytes(4, "little") for one in words)
        held = arm6.Cpu("arm60", arm6.Memory(image=image, fill=0), fill=0)
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

    def test_a_block_store_through_the_user_bank_takes_the_user_registers(self) -> None:
        # Arrange
        held = self.part(0xE8C12000)
        held.registers.write(1, 0x2000)
        in_mode(held, "usr32")
        held.registers.write(13, 0xDEAD)
        in_mode(held, "svc32")
        held.registers.write(13, 0xBEEF)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.memory.read_word(0x2000), 0xDEAD)

    def test_a_block_load_through_the_user_bank_writes_the_user_registers(self) -> None:
        # Arrange
        held = self.part(0xE8D12000)
        held.registers.write(1, 0x2000)
        held.memory.write_word(0x2000, 0xC0DE)

        # Act
        held.step()

        # Assert
        in_mode(held, "usr32")
        self.assertEqual(held.registers.read(13), 0xC0DE)

    def test_a_block_load_of_the_counter_with_the_flag_restores_the_saved_status(self) -> None:
        # Arrange
        held = self.part(0xE8D18000)
        held.registers.write(1, 0x2000)
        held.registers.save(0xF00000D3)
        held.memory.write_word(0x2000, 0x40)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.cpsr, 0xF00000D3)

    def test_a_byte_swap_exchanges_one_byte(self) -> None:
        held = self.part(0xE1420091)
        held.registers.write(2, 0x2000)
        held.registers.write(1, 0x99)
        held.memory.write_word(0x2000, 0x11223344)

        held.step()

        self.assertEqual((held.registers.read(0), held.memory.read_byte(0x2000)), (0x44, 0x99))

    def test_a_coprocessor_data_transfer_with_none_attached_traps(self) -> None:
        # Arrange
        held = self.part(0xED912100)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0x04, quote("coprocessorAbsent"))

    def test_a_coprocessor_register_transfer_with_none_attached_traps_too(self) -> None:
        # Arrange
        held = self.part(0xEE212113)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.pc, 0x04, quote("coprocessorAbsent"))

    def test_a_block_load_of_the_counter_in_a_user_mode_has_no_status_to_restore(self) -> None:
        # Arrange
        held = self.part(0xE8D18000)
        held.registers.write(1, 0x2000)
        in_mode(held, "usr32")
        before = held.registers.cpsr
        held.memory.write_word(0x2000, 0x40)

        # Act
        held.step()

        # Assert
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

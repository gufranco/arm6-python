from __future__ import annotations

import sys
import unittest
from itertools import pairwise
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import (  # noqa: E402
    MODES,
    Clock,
    Cpu,
    Cycles,
    Memory,
    UnspecifiedEncoding,
    Waits,
    disassemble,
)
from conformance.printed import quote, value  # noqa: E402

MOV_R1_5 = 0xE3A01005
MOV_R2_7 = 0xE3A02007
MOV_R1_0X2000 = 0xE3A01A02
MOV_R0_R0 = 0xE1A00000
MUL_R0_R1_R2 = 0xE0000291
MULS_R0_R1_R2 = 0xE0100291
MUL_R3_R2_R1 = 0xE0030192
BRANCH_TO_ITSELF = 0xEAFFFFFE
BRANCH_TO_0X100 = 0xEA00003E
BRANCH_PAST_ONE_WORD = 0xEA000000
LOAD_R0_FROM_R1 = 0xE5910000
LOAD_R0_FROM_PC = 0xE59F0000
LOAD_BYTE_R0_FROM_R1 = 0xE5D10000
STORE_R0_TO_R1 = 0xE5810000
STORE_R0_TO_R1_PLUS_4 = 0xE5810004
SWAP_R0_R1_AT_R2 = 0xE1020091
SWAP_R4_R0_AT_R1 = 0xE1014090
STORE_MANY_R0_R3_R4 = 0xE8810019
LOAD_MANY_R5_R6_R7 = 0xE89100E0
WRITE_FLAGS_FROM_R0 = 0xE128F000
AND_WITH_REGISTER_SHIFT = 0xE0000211
ADD_WITH_REGISTER_SHIFT = 0xE0812013
LONG_MULTIPLY = 0xE0812394
BIT_SEVEN = 1 << 7
CARRY = 1 << 29
MODE_FIELD = 0b11111
DATA = 0x2000
LONG_WAIT = 10**12


def machine(*words: int, bigend: bool = False) -> Cpu:
    image = b"".join(one.to_bytes(4, "big" if bigend else "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0, bigend=bigend), fill=0, bigend=bigend)
    held.registers.pc = 0
    return held


def seen_in(cpu: Cpu, bits: int) -> tuple[object, ...]:
    held = cpu.registers
    current = held.cpsr
    held.cpsr = (current & ~MODE_FIELD) | bits
    seen = (tuple(held.read(index) for index in range(15)), held.saved())
    held.cpsr = current
    return seen


def registers_of(cpu: Cpu) -> tuple[object, ...]:
    banks = tuple(seen_in(cpu, mode.bits) for mode in MODES.values() if mode.wide)
    return (banks, cpu.registers.pc, cpu.registers.cpsr)


def stopped_after_every_cycle(cpu: Cpu, cycles: int) -> tuple[object, ...]:
    with Clock(cpu) as clock:
        clock.run_for(cycles)
        return registers_of(cpu)


def carry_after_a_multiply(multiplicand: int, multiplier: int) -> bool:
    held = machine(MULS_R0_R1_R2)
    held.registers.write(1, multiplicand)
    held.registers.write(2, multiplier)
    held.registers.cpsr = held.registers.cpsr | CARRY
    held.step()
    return bool(held.registers.cpsr & CARRY)


def every_row_of(cpu: Cpu, steps: int) -> list[tuple[str, int]]:
    rows: list[tuple[str, int]] = []
    cpu.on_cycle = lambda one: rows.append(
        (one.bus.cycles[-1].kind.letter, one.bus.cycles[-1].address)
    )
    for _ in range(steps):
        cpu.step()
    return rows


def word_loaded_big_endian(offset: int) -> int:
    held = machine(LOAD_R0_FROM_R1, bigend=True)
    for place, one in enumerate((0x11, 0x22, 0x33, 0x44)):
        held.memory.write_byte(DATA + place, one)
    held.registers.write(1, DATA + offset)
    held.step()
    return held.registers.read(0)


class TheClockTest(unittest.TestCase):
    def test_stopping_the_clock_after_every_cycle_loses_no_state(self) -> None:
        # Arrange
        program = (MOV_R1_5, MOV_R2_7, MUL_R0_R1_R2, BRANCH_TO_ITSELF)
        straight = machine(*program)
        for _ in range(3):
            straight.step()
        clocked = machine(*program)
        printed = (quote("staticImplementation"), quote("noMinimumClock"))

        # Act
        stopped = stopped_after_every_cycle(clocked, straight.cycles + 1)

        # Assert
        self.assertEqual(stopped, registers_of(straight), printed)

    def test_no_wait_figure_is_too_long_for_a_board_to_state(self) -> None:
        # Arrange
        tally = Cycles(s=1, n=1)
        board = Waits(sequential=LONG_WAIT, nonsequential=LONG_WAIT, internal=1, coprocessor=1)

        # Act
        ticks = tally.ticks(board)

        # Assert
        self.assertEqual(ticks, 2 * LONG_WAIT, quote("stretchingAccessTimes"))


class TheMultiplyTest(unittest.TestCase):
    def test_a_multiply_that_sets_flags_leaves_a_carry_that_follows_nothing(self) -> None:
        # Arrange
        operands = [(first, second) for first in range(1, 9) for second in range(1, 9)]

        # Act
        carries = {carry_after_a_multiply(first, second) for first, second in operands}

        # Assert
        self.assertEqual(carries, {True, False}, quote("multiplyCarry"))


class TheResetTest(unittest.TestCase):
    def test_a_reset_spends_the_printed_number_of_dummy_fetches_before_the_vector(self) -> None:
        # Arrange
        held = machine()
        held.registers.pc = 0x1000

        # Act
        held.reset(low_cycles=0)

        # Assert
        kinds = [one.kind.letter for one in held.bus.cycles]
        self.assertEqual(kinds.index("N"), value("resetCost"))


class TheBusTest(unittest.TestCase):
    def test_the_type_a_row_carries_describes_the_address_after_it(self) -> None:
        # Arrange
        held = machine(BRANCH_TO_0X100)

        # Act
        held.step()

        # Assert
        rows = held.bus.cycles
        self.assertEqual(
            [
                (rows[0].kind.letter, rows[1].address == rows[0].address + 4),
                (rows[1].kind.letter, rows[2].address == rows[1].address + 4),
            ],
            [("N", False), ("S", True)],
            quote("cycleTypesPipelined"),
        )

    def test_a_sequential_row_is_followed_by_the_same_address_or_the_next_word(self) -> None:
        # Arrange
        held = machine(
            MOV_R1_0X2000,
            LOAD_R0_FROM_R1,
            MUL_R3_R2_R1,
            STORE_R0_TO_R1_PLUS_4,
            SWAP_R4_R0_AT_R1,
            STORE_MANY_R0_R3_R4,
            LOAD_MANY_R5_R6_R7,
            BRANCH_PAST_ONE_WORD,
            0,
            MOV_R0_R0,
        )

        # Act
        rows = every_row_of(held, 9)

        # Assert
        steps = {
            following - address for (kind, address), (_, following) in pairwise(rows) if kind == "S"
        }
        self.assertEqual(steps, {0, 4}, quote("seqDefinition"))

    def test_a_swap_reads_and_then_writes_with_the_lock_held_across_both(self) -> None:
        # Arrange
        held = machine(SWAP_R0_R1_AT_R2)
        held.registers.write(2, DATA)

        # Act
        held.step()

        # Assert
        accesses = [(one.nrw, one.lock) for one in held.bus.cycles[1:3]]
        self.assertEqual(accesses, [(0, 1), (1, 1)], quote("swapIsLocked"))


class TheEndiannessTest(unittest.TestCase):
    def test_a_part_built_without_saying_how_the_pin_is_tied_is_little_endian(self) -> None:
        # Arrange
        held = Cpu("arm60", fill=0)
        held.memory.write_word(0, STORE_R0_TO_R1)
        held.registers.pc = 0
        held.registers.write(0, 0x11223344)
        held.registers.write(1, DATA)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.memory.read_byte(DATA), 0x44, quote("endianness"))

    def test_a_big_endian_load_at_offset_zero_or_two_puts_that_byte_at_the_top(self) -> None:
        # Arrange
        offsets = (0, 2)

        # Act
        tops = [word_loaded_big_endian(offset) >> 24 for offset in offsets]

        # Assert
        self.assertEqual(tops, [0x11, 0x33], quote("unalignedLoadBigEndian"))

    def test_a_big_endian_byte_load_fills_the_rest_of_the_register_with_zeros(self) -> None:
        # Arrange
        held = machine(LOAD_BYTE_R0_FROM_R1, bigend=True)
        for place, one in enumerate((0xAA, 0xBB, 0xCC, 0xDD)):
            held.memory.write_byte(DATA + place, one)
        held.registers.write(0, 0xFFFFFFFF)
        held.registers.write(1, DATA + 1)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0xBB, quote("byteLoadZeroFilledBigEndian"))


class TheTransfersTest(unittest.TestCase):
    def test_a_word_stored_to_an_unaligned_address_is_not_rotated(self) -> None:
        # Arrange
        held = machine(STORE_R0_TO_R1)
        held.registers.write(0, 0x11223344)
        held.registers.write(1, DATA + 1)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.memory.read_word(DATA), 0x11223344, quote("wordStoreUnaffected"))

    def test_the_counter_as_a_base_is_eight_bytes_past_the_instruction(self) -> None:
        # Arrange
        held = machine(LOAD_R0_FROM_PC, 0, 0xCAFEBABE)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0xCAFEBABE, quote("r15AsBase"))


class TheStatusRegisterTest(unittest.TestCase):
    def test_changing_only_the_flags_preserves_the_reserved_bits(self) -> None:
        # Arrange
        reserved = int(value("reservedBits"), 16)
        held = machine(WRITE_FLAGS_FROM_R0)
        held.registers.cpsr = held.registers.cpsr | reserved
        held.registers.write(0, 0xF0000000)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.cpsr & reserved, reserved, quote("reservedBitsPreserved"))


class TheEncodingsTest(unittest.TestCase):
    def test_a_one_in_bit_seven_of_a_register_shift_leaves_the_data_processing_row(
        self,
    ) -> None:
        # Arrange
        words = (AND_WITH_REGISTER_SHIFT, ADD_WITH_REGISTER_SHIFT)

        # Act
        rows = [disassemble((word | BIT_SEVEN).to_bytes(4, "little"))[0].kind for word in words]

        # Assert
        self.assertEqual(rows, ["multiply", "unspecified"], quote("shiftBitSeven"))

    def test_a_restriction_no_document_here_answers_is_referred_to_the_arm2as(self) -> None:
        # Arrange
        held = machine(LONG_MULTIPLY)
        macrocell = next(
            word for word in quote("arm2asFallback").split() if word.startswith("ARM2")
        )

        # Act
        with self.assertRaises(UnspecifiedEncoding) as refused:
            held.step()

        # Assert
        self.assertIn(macrocell, str(refused.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402
from conformance.printed import quote, value  # noqa: E402

N_BIT = 31
Z_BIT = 30
C_BIT = 29
V_BIT = 28
MODE_FIELD = 0b11111

AND = 0b0000
EOR = 0b0001
SUB = 0b0010
RSB = 0b0011
ADD = 0b0100
ADC = 0b0101
SBC = 0b0110
RSC = 0b0111
TST = 0b1000
TEQ = 0b1001
CMP = 0b1010
CMN = 0b1011
ORR = 0b1100
MOV = 0b1101
BIC = 0b1110
MVN = 0b1111

LSR_BY_ONE = 1 << 7 | 1 << 5

SENTINEL = 0x55


def part(*words: int) -> arm6.Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = arm6.Cpu("arm60", arm6.Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


def in_mode(cpu: arm6.Cpu, name: str) -> arm6.Cpu:
    cpu.registers.cpsr = cpu.registers.cpsr & ~MODE_FIELD | arm6.MODES[name].bits
    return cpu


def with_flag(cpu: arm6.Cpu, bit: int) -> arm6.Cpu:
    cpu.registers.cpsr = cpu.registers.cpsr | 1 << bit
    return cpu


def flag(cpu: arm6.Cpu, bit: int) -> bool:
    return bool(cpu.registers.cpsr >> bit & 1)


def operation(op: int, shift: int = 0) -> int:
    return 0xE0100000 | op << 21 | 1 << 16 | shift | 2


def prepared(op: int, first: int, second: int, carry: bool = False, shift: int = 0) -> arm6.Cpu:
    held = part(operation(op, shift))
    held.registers.write(0, SENTINEL)
    held.registers.write(1, first)
    held.registers.write(2, second)
    return with_flag(held, C_BIT) if carry else held


def moved(field: int, carry: bool = False) -> arm6.Cpu:
    held = part(0xE3B00000 | field)
    return with_flag(held, C_BIT) if carry else held


def loaded(word: int, mode: str, given: dict[int, int]) -> arm6.Cpu:
    held = in_mode(part(word), mode)
    for index, one in given.items():
        held.registers.write(index, one)
    return held


def stepped(parts: list[arm6.Cpu]) -> list[int]:
    return [one.step() for one in parts]


class TheLogicalOperationsTest(unittest.TestCase):
    def test_each_logical_operation_writes_its_printed_result(self) -> None:
        # Arrange
        cases = [
            (AND, 0xFF00FF00, 0x0FF00FF0, 0x0F000F00),
            (EOR, 0xFF00FF00, 0x0FF00FF0, 0xF0F0F0F0),
            (ORR, 0xFF00FF00, 0x0FF00FF0, 0xFFF0FFF0),
            (MOV, 0x11111111, 0x22222222, 0x22222222),
            (BIC, 0xFFFFFFFF, 0x0000FFFF, 0xFFFF0000),
            (MVN, 0, 0x0000FFFF, 0xFFFF0000),
        ]
        parts = [prepared(op, first, second) for op, first, second, _ in cases]

        # Act
        stepped(parts)

        # Assert
        self.assertEqual([one.registers.read(0) for one in parts], [one[3] for one in cases])

    def test_a_logical_operation_leaves_the_overflow_flag_alone(self) -> None:
        # Arrange
        held = with_flag(prepared(AND, 0xFFFFFFFF, 0xFFFFFFFF), V_BIT)

        # Act
        held.step()

        # Assert
        self.assertTrue(flag(held, V_BIT))

    def test_n_and_z_are_the_top_bit_and_the_all_zeros_test_of_the_result(self) -> None:
        # Arrange
        parts = [prepared(AND, 0xFF00, 0x00FF), prepared(MOV, 0, 0x80000000)]

        # Act
        stepped(parts)

        # Assert
        held = [(flag(one, N_BIT), flag(one, Z_BIT)) for one in parts]
        self.assertEqual(held, [(False, True), (True, False)])

    def test_and_takes_its_carry_from_the_shifter_rather_than_the_adder(self) -> None:
        # Arrange
        held = prepared(AND, 0xFFFFFFFF, 1, shift=LSR_BY_ONE)

        # Act
        held.step()

        # Assert
        held_flags = (held.registers.read(0), flag(held, C_BIT))
        self.assertEqual(held_flags, (0, True), quote("logicalFlags"))


class TheArithmeticOperationsTest(unittest.TestCase):
    def test_each_arithmetic_operation_writes_its_printed_result(self) -> None:
        # Arrange
        cases = [
            (ADD, 2, 3, False, 5),
            (SUB, 5, 3, False, 2),
            (RSB, 3, 5, False, 2),
            (ADC, 2, 3, True, 6),
            (SBC, 5, 3, False, 1),
            (SBC, 5, 3, True, 2),
            (RSC, 3, 5, True, 2),
        ]
        parts = [prepared(op, first, second, carry) for op, first, second, carry, _ in cases]

        # Act
        stepped(parts)

        # Assert
        self.assertEqual([one.registers.read(0) for one in parts], [one[4] for one in cases])

    def test_a_sum_that_leaves_the_word_carries_out_of_bit_thirty_one(self) -> None:
        # Arrange
        held = prepared(ADD, 0xFFFFFFFF, 1)

        # Act
        held.step()

        # Assert
        held_flags = (held.registers.read(0), flag(held, C_BIT))
        self.assertEqual(held_flags, (0, True), quote("arithmeticFlags"))

    def test_carry_and_overflow_are_the_ones_each_worked_example_gives(self) -> None:
        # Arrange
        cases = [
            (SUB, 5, 3, (True, False)),
            (SUB, 3, 5, (False, False)),
            (ADD, 0x7FFFFFFF, 1, (False, True)),
            (ADD, 1, 1, (False, False)),
            (SUB, 0x80000000, 1, (True, True)),
        ]
        parts = [prepared(op, first, second) for op, first, second, _ in cases]

        # Act
        stepped(parts)

        # Assert
        held = [(flag(one, C_BIT), flag(one, V_BIT)) for one in parts]
        self.assertEqual(held, [one[3] for one in cases])

    def test_an_arithmetic_operation_touches_the_overflow_flag(self) -> None:
        # Arrange
        held = with_flag(prepared(ADD, 1, 1), V_BIT)

        # Act
        held.step()

        # Assert
        self.assertFalse(flag(held, V_BIT))


class TheFourThatWriteNoResultTest(unittest.TestCase):
    def test_tst_teq_cmp_and_cmn_write_nothing(self) -> None:
        # Arrange
        parts = [prepared(op, 0xFF, 0xFF) for op in (TST, TEQ, CMP, CMN)]

        # Act
        stepped(parts)

        # Assert
        self.assertEqual([one.registers.read(0) for one in parts], [SENTINEL] * 4)

    def test_but_they_still_produce_flags(self) -> None:
        # Arrange
        held = prepared(CMP, 5, 5)

        # Act
        held.step()

        # Assert
        self.assertEqual((flag(held, Z_BIT), flag(held, C_BIT)), (True, True))

    def test_and_everything_else_writes(self) -> None:
        # Arrange
        parts = [prepared(op, 0, 0) for op in range(16)]

        # Act
        stepped(parts)

        # Assert
        writing = [op for op, one in enumerate(parts) if one.registers.read(0) != SENTINEL]
        self.assertEqual(writing, [AND, EOR, SUB, RSB, ADD, ADC, SBC, RSC, ORR, MOV, BIC, MVN])


class TheImmediateOperandTest(unittest.TestCase):
    def test_an_immediate_is_its_byte_turned_and_a_turned_one_carries_bit_31(self) -> None:
        # Arrange
        parts = [moved(0x0FF), moved(0x102)]

        # Act
        stepped(parts)

        # Assert
        held = [(one.registers.read(0), flag(one, C_BIT)) for one in parts]
        self.assertEqual(held, [(0xFF, False), (0x80000000, True)], quote("immediateRotateCarry"))

    def test_an_unrotated_immediate_leaves_the_carry_alone(self) -> None:
        # Arrange
        held = moved(0x0FF, carry=True)

        # Act
        held.step()

        # Assert
        self.assertTrue(flag(held, C_BIT), quote("immediateRotateCarry"))

    def test_the_rotate_field_turns_the_byte_by_twice_its_value(self) -> None:
        # Arrange
        held = moved(0x101)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x40000000, quote("immediateRotate"))

    def test_every_power_of_two_is_reachable_as_an_immediate(self) -> None:
        # Arrange
        parts = [moved(rotate << 8 | 1) for rotate in range(16)]

        # Act
        stepped(parts)

        # Assert
        held = sorted(one.registers.read(0) for one in parts)
        self.assertEqual(held, [1 << bit for bit in range(0, 32, 2)])


class DrivenAsWholeInstructionsTest(unittest.TestCase):
    def test_each_instruction_leaves_the_register_and_zero_flag_its_example_gives(self) -> None:
        # Arrange
        cases = [
            (0xE3A00001, {}, (1, False)),
            (0xE3A00102, {}, (0x80000000, False)),
            (0xE3B00000, {}, (0, True)),
            (0xE3300001, {0: 0x77}, (0x77, False)),
            (0xE3500005, {0: 5}, (5, True)),
            (0xE0203291, {1: 6, 2: 7, 3: 8}, (50, False)),
            (0xE1000000, {0: 0x55}, (0x55, False)),
        ]
        parts = [loaded(word, "svc32", given) for word, given, _ in cases]

        # Act
        stepped(parts)

        # Assert
        held = [(one.registers.read(0), flag(one, Z_BIT)) for one in parts]
        self.assertEqual(held, [one[2] for one in cases])

    def test_each_status_write_leaves_the_status_register_its_example_gives(self) -> None:
        # Arrange
        cases = [
            (0xE129F000, "svc32", 0xF00000D1, 0xF00000D1),
            (0xE128F000, "svc32", 0xF0000010, 0xF0000013),
            (0xE128F000, "svc32", 0xF0000000, 0xF0000013),
            (0xE328F20F, "svc32", 0, 0xF0000013),
            (0xE129F000, "usr32", 0x000000D1, 0x00000010),
            (0xE129F000, "usr32", 0xF00000D1, 0xF0000010),
        ]
        parts = [loaded(word, mode, {0: given}) for word, mode, given, _ in cases]

        # Act
        stepped(parts)

        # Assert
        self.assertEqual([one.registers.cpsr for one in parts], [one[3] for one in cases])

    def test_the_counter_read_as_an_operand_is_eight_bytes_ahead(self) -> None:
        # Arrange
        held = part(0xE28F0000)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), value("prefetchOffset")[0])

    def test_and_twelve_bytes_ahead_when_a_register_supplies_the_shift(self) -> None:
        # Arrange
        held = part(0xE1A0001F)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), value("prefetchOffset")[1])

    def test_reading_the_status_register_into_a_register(self) -> None:
        # Arrange
        held = with_flag(part(0xE10F0000), N_BIT)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x80000013)

    def test_reading_the_saved_status_register_into_a_register(self) -> None:
        # Arrange
        held = part(0xE14F0000)
        held.registers.save(0x600000D3)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x600000D3)

    def test_reading_a_saved_status_register_a_user_mode_does_not_have(self) -> None:
        # Arrange
        held = in_mode(part(0xE14F0000), "usr32")

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(0), 0x00000010)

    def test_writing_the_saved_status_register_from_a_register(self) -> None:
        # Arrange
        held = part(0xE169F000)
        held.registers.write(0, 0xF00000D1)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.saved(), 0xF00000D1)

    def test_writing_a_saved_status_register_a_user_mode_does_not_have(self) -> None:
        # Arrange
        held = part(0xE169F000)
        held.registers.save(0x600000D3)
        in_mode(held, "usr32").registers.write(0, 0xF00000D1)

        # Act
        held.step()

        # Assert
        self.assertEqual(in_mode(held, "svc32").registers.saved(), 0x600000D3)

    def test_the_reserved_bits_are_written_rather_than_masked_away(self) -> None:
        # Arrange
        held = part(0xE129F000)
        held.registers.cpsr = held.registers.cpsr | int(value("reservedBits"), 16)
        held.registers.write(0, 0x000000D3)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.cpsr, 0x000000D3)

    def test_the_form_earlier_parts_spelled_teqp_restores_the_saved_status(self) -> None:
        # Arrange
        held = part(0xE130F000)
        held.registers.save(0xF00000D3)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.cpsr, 0xF00000D3, quote("teqp"))

    def test_and_does_nothing_at_all_in_a_user_mode(self) -> None:
        # Arrange
        held = in_mode(part(0xE130F000), "usr32")

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.cpsr, 0x00000010, quote("teqp"))

    def test_writing_the_counter_with_the_flag_set_restores_the_saved_status(self) -> None:
        # Arrange
        held = part(0xE1B0F000)
        held.registers.save(0xF00000D3)
        held.registers.write(0, 0x40)

        # Act
        held.step()

        # Assert
        self.assertEqual(
            (held.registers.pc, held.registers.cpsr), (0x40, 0xF00000D3), quote("writingR15")
        )

    def test_a_multiply_that_sets_flags_reports_a_zero_result_as_zero(self) -> None:
        # Arrange
        held = part(0xE0100291)
        held.registers.write(1, 0)
        held.registers.write(2, 5)

        # Act
        held.step()

        # Assert
        self.assertEqual((flag(held, Z_BIT), flag(held, N_BIT)), (True, False))

    def test_a_multiply_accumulate_whose_destination_is_its_multiplicand_is_meaningless(
        self,
    ) -> None:
        # Arrange
        held = part(0xE0213291)
        held.registers.write(1, 6)
        held.registers.write(2, 7)
        held.registers.write(3, 8)

        # Act
        held.step()

        # Assert
        self.assertEqual(held.registers.read(1), 8, quote("multiplyRdEqualsRm"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

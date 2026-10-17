from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402
from conformance.printed import quote, value  # noqa: E402

WHOLE_WORD = 0xFFFFFFFF

MODE_FIELD = 0b11111

SUPERVISOR = 0b10011

CONDITIONAL_MOVES = (0x43A00001, 0x03A01001, 0x23A02001, 0x63A03001)

ALWAYS_MOVE = 0xE3A04001

FLAG_TESTED_BY = {0: "N", 1: "Z", 2: "C", 3: "V"}

SOFTWARE_INTERRUPT = 0xEF000000

MOVS_ZERO = 0xE3B00000

MOVS_ONE = 0xE3B00001


def part(*words: int) -> Any:
    data = b"".join(word.to_bytes(4, "little") for word in words)
    return arm6.Cpu("arm60", arm6.Memory(image=data, fill=0), fill=0).reset()


def behaviour(cpsr: int) -> tuple[object, ...]:
    program = (*CONDITIONAL_MOVES, ALWAYS_MOVE)
    cpu = part(*program)
    cpu.registers.cpsr = cpsr
    mode = cpu.mode.name
    cpu.run_for(len(program))
    passed = tuple(cpu.registers.read(one) for one in range(len(program)))
    return (mode, passed, cpu.irq(), cpu.fiq())


def bits_that_change(answer: Any) -> set[int]:
    before = answer(SUPERVISOR)
    return {bit for bit in range(32) if answer(SUPERVISOR ^ 1 << bit) != before}


def observable_bits() -> set[int]:
    return bits_that_change(behaviour)


def passed_with(cpsr: int) -> tuple[int, ...]:
    cpu = part(*CONDITIONAL_MOVES)
    cpu.registers.cpsr = cpsr
    cpu.run_for(len(CONDITIONAL_MOVES))
    return tuple(cpu.registers.read(one) for one in range(len(CONDITIONAL_MOVES)))


def conditions_passed_by_each_bit() -> dict[int, set[str]]:
    found: dict[int, set[str]] = {}
    for bit in range(32):
        passed = passed_with(SUPERVISOR ^ 1 << bit)
        if any(passed):
            found[bit] = {FLAG_TESTED_BY[place] for place, one in enumerate(passed) if one}
    return found


def as_mask(bits: set[int]) -> int:
    return sum(1 << bit for bit in bits)


def mode_after_writing(cpsr: int) -> Any:
    cpu = part()
    cpu.registers.cpsr = cpsr
    return cpu.mode


def accepted_encodings() -> set[int]:
    found: set[int] = set()
    for bits in range(MODE_FIELD + 1):
        try:
            mode_after_writing(bits)
        except arm6.UnknownMode:
            continue
        found.add(bits)
    return found


def stepped_from(cpsr: int, word: int) -> int:
    cpu = part(word)
    cpu.registers.cpsr = cpsr
    cpu.step()
    return int(cpu.registers.cpsr)


class TheBitsTheDatasheetDrawsTest(unittest.TestCase):
    def test_the_condition_flags_sit_at_the_top(self) -> None:
        # Arrange
        drawn = {31: {"N"}, 30: {"Z"}, 29: {"C"}, 28: {"V"}}

        # Act
        found = conditions_passed_by_each_bit()

        # Assert
        self.assertEqual(found, drawn)

    def test_the_two_interrupt_disables_sit_below_them(self) -> None:
        # Arrange
        enabled = (True, True)

        # Act
        found = bits_that_change(lambda cpsr: behaviour(cpsr)[2:] != enabled)

        # Assert
        self.assertEqual(found, {7, 6})

    def test_the_mode_field_is_the_bottom_five_bits(self) -> None:
        # Arrange
        supervisor = "svc32"

        # Act
        found = bits_that_change(lambda cpsr: behaviour(cpsr)[0] == supervisor)

        # Assert
        self.assertEqual(as_mask(found), MODE_FIELD)

    def test_the_reserved_bits_are_the_ones_the_datasheet_lists(self) -> None:
        # Arrange
        printed = int(value("reservedBits"), 16)

        # Act
        found = observable_bits()

        # Assert
        self.assertEqual(WHOLE_WORD ^ as_mask(found), printed)

    def test_bit_five_is_reserved_rather_than_a_thumb_bit(self) -> None:
        # Arrange
        thumb = 5

        # Act
        found = observable_bits()

        # Assert
        self.assertNotIn(thumb, found)

    def test_the_defined_and_the_reserved_bits_between_them_are_the_whole_word(self) -> None:
        # Arrange
        reserved = int(value("reservedBits"), 16)

        # Act
        found = observable_bits()

        # Assert
        self.assertEqual(as_mask(found) | reserved, WHOLE_WORD)

    def test_and_no_bit_is_in_both(self) -> None:
        # Arrange
        reserved = int(value("reservedBits"), 16)

        # Act
        found = observable_bits()

        # Assert
        self.assertEqual(as_mask(found) & reserved, 0)

    def test_eleven_bits_are_defined_as_the_datasheet_says(self) -> None:
        # Arrange
        defined = 11

        # Act
        found = observable_bits()

        # Assert
        self.assertEqual(len(found), defined)


class TenModesInTwoOverlappingSetsTest(unittest.TestCase):
    def test_there_are_ten_of_them(self) -> None:
        # Arrange
        printed = value("modesAvailable")

        # Act
        found = accepted_encodings()

        # Assert
        self.assertEqual((len(found), len(arm6.MODES)), (printed, printed))

    def test_the_thirty_two_bit_encodings_are_the_ones_table_one_gives(self) -> None:
        # Arrange
        table_one = {
            0b10000: "usr32",
            0b10001: "fiq32",
            0b10010: "irq32",
            0b10011: "svc32",
            0b10111: "abt32",
            0b11011: "und32",
        }

        # Act
        found = {bits: mode_after_writing(bits) for bits in table_one}

        # Assert
        self.assertEqual(
            {bits: (one.name, one.wide) for bits, one in found.items()},
            {bits: (name, True) for bits, name in table_one.items()},
        )

    def test_the_twenty_six_bit_encodings_are_the_ones_the_application_note_gives(self) -> None:
        # Arrange
        printed = {bits: name for name, bits in value("modes26bit").items()}

        # Act
        found = {bits: mode_after_writing(bits) for bits in printed}

        # Assert
        self.assertEqual(
            {bits: (one.name, one.wide) for bits, one in found.items()},
            {bits: (name, False) for bits, name in printed.items()},
        )

    def test_no_other_encoding_is_accepted(self) -> None:
        # Arrange
        printed = {0b10000, 0b10001, 0b10010, 0b10011, 0b10111, 0b11011}
        printed |= set(value("modes26bit").values())

        # Act
        found = accepted_encodings()

        # Assert
        self.assertEqual(found, printed)

    def test_only_the_two_user_modes_are_unprivileged(self) -> None:
        # Arrange
        modes = arm6.MODES.values()

        # Act
        found = sorted(one.name for one in modes if not one.privileged)

        # Assert
        self.assertEqual(found, ["usr26", "usr32"])

    def test_each_mode_names_the_bank_it_shares_with_its_partner(self) -> None:
        # Arrange
        modes = arm6.MODES

        # Act
        found = {name: one.bank for name, one in modes.items()}

        # Assert
        self.assertEqual(
            found,
            {
                **{"usr26": "usr", "usr32": "usr", "fiq26": "fiq", "fiq32": "fiq"},
                **{"irq26": "irq", "irq32": "irq", "svc26": "svc", "svc32": "svc"},
                **{"abt32": "abt", "und32": "und"},
            },
        )

    def test_a_user_mode_has_no_saved_status_register(self) -> None:
        # Arrange
        modes = arm6.MODES

        # Act
        found = (modes["usr32"].spsr, modes["usr26"].spsr)

        # Assert
        self.assertEqual(found, (None, None))

    def test_and_there_are_five_saved_status_registers_in_all(self) -> None:
        # Arrange
        modes = arm6.MODES.values()

        # Act
        found = sorted({one.spsr for one in modes if one.spsr is not None})

        # Assert
        self.assertEqual(found, ["abt", "fiq", "irq", "svc", "und"])

    def test_a_mode_says_what_it_is_when_printed(self) -> None:
        # Arrange
        supervisor = arm6.MODES["svc32"]

        # Act
        shown = repr(supervisor)

        # Assert
        self.assertEqual(shown, "Mode(svc32, bits=0b10011)")


class ReadingAndWritingTheFieldTest(unittest.TestCase):
    def test_the_mode_is_read_out_of_the_bottom_five_bits(self) -> None:
        # Arrange
        cpsr = 0xF0000000 | SUPERVISOR

        # Act
        found = mode_after_writing(cpsr)

        # Assert
        self.assertEqual(found.name, "svc32")

    def test_reading_an_encoding_no_mode_uses_is_refused_rather_than_guessed(self) -> None:
        # Arrange
        unused = 0b10100

        # Act
        with self.assertRaises(arm6.UnknownMode, msg=quote("modeBitsOnlyDescribed")) as refused:
            mode_after_writing(unused)

        # Assert
        self.assertIn(f"0b{unused:05b}", str(refused.exception))

    def test_system_mode_is_not_among_them_and_the_refusal_names_it(self) -> None:
        # Arrange
        system = 0b11111

        # Act
        with self.assertRaises(arm6.UnknownMode) as caught:
            mode_after_writing(system)

        # Assert
        self.assertIn("11111", str(caught.exception))

    def test_entering_an_exception_changes_the_mode_and_leaves_the_flags_alone(self) -> None:
        # Arrange
        user_with_every_flag = 0xF0000000 | 0b10000

        # Act
        found = stepped_from(user_with_every_flag, SOFTWARE_INTERRUPT)

        # Assert
        self.assertEqual(found, 0xF0000000 | 1 << 7 | SUPERVISOR)

    def test_a_result_of_zero_sets_the_flag_where_the_figure_draws_it(self) -> None:
        # Arrange
        supervisor_and_clear = 0xC0 | SUPERVISOR

        # Act
        found = stepped_from(supervisor_and_clear, MOVS_ZERO)

        # Assert
        self.assertEqual(found, 1 << 30 | 0xC0 | SUPERVISOR)

    def test_and_clearing_two_flags_leaves_the_others(self) -> None:
        # Arrange
        every_flag = 0xF0000000 | 0xC0 | SUPERVISOR

        # Act
        found = stepped_from(every_flag, MOVS_ONE)

        # Assert
        self.assertEqual(found, 0x30000000 | 0xC0 | SUPERVISOR)


if __name__ == "__main__":
    unittest.main(verbosity=2)

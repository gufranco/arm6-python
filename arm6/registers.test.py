from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import arm6  # noqa: E402
from conformance.printed import quote, value  # noqa: E402

MODE_FIELD = 0b11111

THIRTY_TWO_BIT_MODES = ("usr32", "fiq32", "irq32", "svc32", "abt32", "und32")


def switch(held: Any, name: str) -> Any:
    held.cpsr = (held.cpsr & ~MODE_FIELD) | arm6.MODES[name].bits
    return held


def in_mode(name: str, seed: int = 1) -> Any:
    return switch(arm6.Registers(seed=seed), name)


def written_in_each_mode(held: Any, index: int) -> dict[str, int]:
    for place, name in enumerate(arm6.MODES):
        switch(held, name).write(index, 0x100 + place)
    return {name: switch(held, name).read(index) for name in arm6.MODES}


def saved_in_each_mode(held: Any) -> dict[str, int | None]:
    for place, name in enumerate(THIRTY_TWO_BIT_MODES):
        switch(held, name).save(0x200 + place)
    return {name: switch(held, name).saved() for name in THIRTY_TWO_BIT_MODES}


def saved_after_a_save_in(held: Any, mode: str, saved: int) -> dict[str, int | None]:
    switch(held, mode).save(saved)
    return {name: switch(held, name).saved() for name in THIRTY_TWO_BIT_MODES}


def written_then_read_elsewhere(held: Any, index: int, value: int, other: str) -> int:
    held.write(index, value)
    return int(switch(held, other).read(index))


class ThirtySevenRegistersTest(unittest.TestCase):
    def test_thirty_one_of_them_are_general_purpose(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)

        # Act
        general = held.general_count()

        # Assert
        self.assertEqual(general, 31)

    def test_and_six_are_status_registers(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)

        # Act
        status = held.status_count()

        # Assert
        self.assertEqual(status, 6)

    def test_which_is_thirty_seven_in_all(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)

        # Act
        total = held.general_count() + held.status_count()

        # Assert
        self.assertEqual(total, value("registerCount"))


class NothingStartsClearedTest(unittest.TestCase):
    def test_the_registers_do_not_come_up_zero(self) -> None:
        # Arrange
        held = arm6.Registers(seed=7)

        # Act
        values = {held.read(one) for one in range(15)}

        # Assert
        self.assertNotEqual(values, {0})

    def test_the_same_seed_scrambles_the_same_way(self) -> None:
        # Arrange
        first = arm6.Registers(seed=99)

        # Act
        second = arm6.Registers(seed=99)

        # Assert
        self.assertEqual(
            [first.read(one) for one in range(16)], [second.read(one) for one in range(16)]
        )

    def test_a_different_seed_scrambles_differently(self) -> None:
        # Arrange
        first = arm6.Registers(seed=1)

        # Act
        second = arm6.Registers(seed=2)

        # Assert
        self.assertIn(True, [first.read(one) != second.read(one) for one in range(16)])

    def test_the_program_counter_comes_up_holding_rubbish_too(self) -> None:
        # Arrange
        held = arm6.Registers(seed=3)

        # Act
        counter = held.pc

        # Assert
        self.assertNotEqual(counter, 0)

    def test_a_caller_who_asks_for_one_value_everywhere_gets_it(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1, fill=0)

        # Act
        values = {held.read(one) for one in range(16)}

        # Assert
        self.assertEqual(values, {0})


class TheLowRegistersAreNeverBankedTest(unittest.TestCase):
    def test_a_write_in_one_mode_is_seen_in_another(self) -> None:
        # Arrange
        held = in_mode("usr32")

        # Act
        found = written_then_read_elsewhere(held, 3, 0x1234, "fiq32")

        # Assert
        self.assertEqual(found, 0x1234)

    def test_and_that_holds_at_the_top_of_the_unbanked_run(self) -> None:
        # Arrange
        held = in_mode("usr32")

        # Act
        found = written_then_read_elsewhere(held, 7, 0x5678, "und32")

        # Assert
        self.assertEqual(found, 0x5678)


class FiqBanksSevenTest(unittest.TestCase):
    def test_the_five_above_the_common_run_are_the_fiq_mode_s_own(self) -> None:
        # Arrange
        held = in_mode("usr32")

        # Act
        found = {index: written_in_each_mode(held, index) for index in range(8, 13)}

        # Assert
        self.assertEqual(
            {index: (by_mode["usr32"], by_mode["fiq32"]) for index, by_mode in found.items()},
            dict.fromkeys(range(8, 13), (0x109, 0x107)),
        )

    def test_and_the_fiq_copies_survive_the_trip_back(self) -> None:
        # Arrange
        held = in_mode("fiq32")
        held.write(10, 0xBEEF)
        switch(held, "usr32").write(10, 0xFACE)

        # Act
        found = switch(held, "fiq32").read(10)

        # Assert
        self.assertEqual(found, 0xBEEF)

    def test_no_other_privileged_mode_banks_them(self) -> None:
        # Arrange
        held = in_mode("usr32")

        # Act
        found = written_then_read_elsewhere(held, 9, 0x11, "irq32")

        # Assert
        self.assertEqual(found, 0x11)


class EveryPrivilegedModeBanksTwoTest(unittest.TestCase):
    def test_the_stack_pointer_is_the_mode_s_own(self) -> None:
        # Arrange
        held = in_mode("usr32")
        held.write(13, 0x1000)
        switch(held, "svc32").write(13, 0x2000)

        # Act
        found = switch(held, "usr32").read(13)

        # Assert
        self.assertEqual(found, 0x1000)

    def test_and_so_is_the_link_register(self) -> None:
        # Arrange
        held = in_mode("abt32")
        held.write(14, 0xAB0)
        switch(held, "und32").write(14, 0x000)

        # Act
        found = switch(held, "abt32").read(14)

        # Assert
        self.assertEqual(found, 0xAB0)

    def test_there_are_six_banks_of_them(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)

        # Act
        found = written_in_each_mode(held, 13)

        # Assert
        self.assertEqual(len(set(found.values())), 6)


class TheTwoSetsShareTheirBanksTest(unittest.TestCase):
    def test_the_twenty_six_bit_user_mode_shares_the_thirty_two_bit_one_s(self) -> None:
        # Arrange
        held = in_mode("usr32")

        # Act
        found = written_then_read_elsewhere(held, 13, 0xC0DE, "usr26")

        # Assert
        self.assertEqual(found, 0xC0DE)

    def test_and_the_two_fiq_modes_share_the_seven(self) -> None:
        # Arrange
        held = in_mode("fiq32")

        # Act
        found = written_then_read_elsewhere(held, 11, 0x7777, "fiq26")

        # Assert
        self.assertEqual(found, 0x7777)


class TheSavedStatusRegistersTest(unittest.TestCase):
    def test_there_are_five_of_them(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)

        # Act
        found = saved_in_each_mode(held)

        # Assert
        self.assertEqual(
            found,
            {"usr32": None, "fiq32": 0x201, "irq32": 0x202}
            | {"svc32": 0x203, "abt32": 0x204, "und32": 0x205},
        )

    def test_a_user_mode_has_none_to_read(self) -> None:
        # Arrange
        held = in_mode("usr32")

        # Act
        saved = held.saved()

        # Assert
        self.assertIsNone(saved)

    def test_a_privileged_mode_reads_its_own(self) -> None:
        # Arrange
        held = in_mode("irq32")
        held.save(0x600000D3)
        switch(held, "svc32").save(0x000000D3)

        # Act
        saved = switch(held, "irq32").saved()

        # Assert
        self.assertEqual(saved, 0x600000D3)

    def test_writing_one_in_a_user_mode_changes_nothing(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)
        before = saved_in_each_mode(held)

        # Act
        after = saved_after_a_save_in(held, "usr32", 0x12345678)

        # Assert
        self.assertEqual(after, before)

    def test_writing_one_in_a_privileged_mode_lands_in_that_bank(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)
        before = saved_in_each_mode(held)

        # Act
        after = saved_after_a_save_in(held, "und32", 0x000000DB)

        # Assert
        self.assertEqual(after, before | {"und32": 0x000000DB})


class TheProgramCounterTest(unittest.TestCase):
    def test_reading_it_clears_the_bottom_two_bits(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1, fill=0)
        held.pc = 0x1006

        # Act
        counter = held.read(15)

        # Assert
        self.assertEqual(counter, 0x1004, quote("r15Read"))

    def test_writing_it_goes_to_the_counter_rather_than_to_a_bank(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1, fill=0)

        # Act
        held.write(15, 0x8000)

        # Assert
        self.assertEqual(held.pc, 0x8000)

    def test_a_value_wider_than_the_bus_is_masked_rather_than_kept(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1, fill=0)

        # Act
        held.write(0, 0x1_0000_0001)

        # Assert
        self.assertEqual(held.read(0), 1)


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_register_file_refuses_a_name_it_does_not_have(self) -> None:
        # Arrange
        held = arm6.Registers(seed=1)

        # Act
        with self.assertRaises(AttributeError) as refused:
            held.q = 1  # type: ignore[attr-defined]

        # Assert
        self.assertIn("q", str(refused.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

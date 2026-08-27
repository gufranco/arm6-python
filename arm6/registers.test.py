"""That thirty seven registers bank the way the programmer's model banks them.

ARM60 page 10 states the count outright: thirty one general purpose registers and
six status registers. Page 1 of the same document says twenty seven, which is the
earlier part's number carried into the text when it was adapted, and the block
diagram on page 2 agrees with page 10 rather than with page 1.

FIQ banks seven registers and every other privileged mode banks two. The four
26-bit modes share their banks with the 32-bit modes of the same name, which is
Application Note 11 rather than the datasheet.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import psr  # noqa: E402
from arm6.registers import Registers  # noqa: E402


def in_mode(name: str, seed: int = 1) -> Registers:
    held = Registers(seed=seed)
    held.cpsr = psr.with_mode(held.cpsr, psr.MODES[name])
    return held


class ThirtySevenRegistersTest(unittest.TestCase):
    def test_thirty_one_of_them_are_general_purpose(self) -> None:
        held = Registers(seed=1)

        general = held.general_count()

        self.assertEqual(general, 31)

    def test_and_six_are_status_registers(self) -> None:
        held = Registers(seed=1)

        status = held.status_count()

        self.assertEqual(status, 6)

    def test_which_is_thirty_seven_in_all(self) -> None:
        held = Registers(seed=1)

        total = held.general_count() + held.status_count()

        self.assertEqual(total, 37)


class NothingStartsClearedTest(unittest.TestCase):
    def test_the_registers_do_not_come_up_zero(self) -> None:
        held = Registers(seed=7)

        values = {held.read(one) for one in range(15)}

        self.assertNotEqual(values, {0})

    def test_the_same_seed_scrambles_the_same_way(self) -> None:
        first = Registers(seed=99)
        second = Registers(seed=99)

        same = [first.read(one) == second.read(one) for one in range(16)]

        self.assertTrue(all(same))

    def test_a_different_seed_scrambles_differently(self) -> None:
        first = Registers(seed=1)
        second = Registers(seed=2)

        differ = [first.read(one) != second.read(one) for one in range(16)]

        self.assertIn(True, differ)

    def test_the_program_counter_comes_up_holding_rubbish_too(self) -> None:
        held = Registers(seed=3)

        counter = held.pc

        self.assertNotEqual(counter, 0)

    def test_a_caller_who_asks_for_one_value_everywhere_gets_it(self) -> None:
        held = Registers(seed=1, fill=0)

        values = {held.read(one) for one in range(16)}

        self.assertEqual(values, {0})


class TheLowRegistersAreNeverBankedTest(unittest.TestCase):
    def test_a_write_in_one_mode_is_seen_in_another(self) -> None:
        held = in_mode("usr32")
        held.write(3, 0x1234)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["fiq32"])

        self.assertEqual(held.read(3), 0x1234)

    def test_and_that_holds_at_the_top_of_the_unbanked_run(self) -> None:
        held = in_mode("usr32")
        held.write(7, 0x5678)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["und32"])

        self.assertEqual(held.read(7), 0x5678)


class FiqBanksSevenTest(unittest.TestCase):
    def test_the_five_above_the_common_run_are_the_fiq_mode_s_own(self) -> None:
        held = in_mode("usr32")
        for one in range(8, 13):
            held.write(one, 0xA0 + one)
        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["fiq32"])

        for one in range(8, 13):
            held.write(one, 0xF0 + one)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["usr32"])
        self.assertEqual([held.read(one) for one in range(8, 13)], [0xA0 + o for o in range(8, 13)])

    def test_and_the_fiq_copies_survive_the_trip_back(self) -> None:
        held = in_mode("fiq32")
        held.write(10, 0xBEEF)
        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["usr32"])
        held.write(10, 0xFACE)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["fiq32"])

        self.assertEqual(held.read(10), 0xBEEF)

    def test_no_other_privileged_mode_banks_them(self) -> None:
        held = in_mode("usr32")
        held.write(9, 0x11)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["irq32"])

        self.assertEqual(held.read(9), 0x11)


class EveryPrivilegedModeBanksTwoTest(unittest.TestCase):
    def test_the_stack_pointer_is_the_mode_s_own(self) -> None:
        held = in_mode("usr32")
        held.write(13, 0x1000)
        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["svc32"])

        held.write(13, 0x2000)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["usr32"])
        self.assertEqual(held.read(13), 0x1000)

    def test_and_so_is_the_link_register(self) -> None:
        held = in_mode("abt32")
        held.write(14, 0xAB0)
        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["und32"])

        held.write(14, 0x000)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["abt32"])
        self.assertEqual(held.read(14), 0xAB0)

    def test_there_are_six_banks_of_them(self) -> None:
        held = Registers(seed=1)

        banks = sorted(held.banked)

        self.assertEqual(banks, ["abt", "fiq", "irq", "svc", "und", "usr"])


class TheTwoSetsShareTheirBanksTest(unittest.TestCase):
    def test_the_twenty_six_bit_user_mode_shares_the_thirty_two_bit_one_s(self) -> None:
        held = in_mode("usr32")
        held.write(13, 0xC0DE)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["usr26"])

        self.assertEqual(held.read(13), 0xC0DE)

    def test_and_the_two_fiq_modes_share_the_seven(self) -> None:
        held = in_mode("fiq32")
        held.write(11, 0x7777)

        held.cpsr = psr.with_mode(held.cpsr, psr.MODES["fiq26"])

        self.assertEqual(held.read(11), 0x7777)


class TheSavedStatusRegistersTest(unittest.TestCase):
    def test_there_are_five_of_them(self) -> None:
        held = Registers(seed=1)

        banks = sorted(held.spsr)

        self.assertEqual(banks, ["abt", "fiq", "irq", "svc", "und"])

    def test_a_user_mode_has_none_to_read(self) -> None:
        held = in_mode("usr32")

        saved = held.saved()

        self.assertIsNone(saved)

    def test_a_privileged_mode_reads_its_own(self) -> None:
        held = in_mode("irq32")
        held.spsr["irq"] = 0x600000D3

        saved = held.saved()

        self.assertEqual(saved, 0x600000D3)

    def test_writing_one_in_a_user_mode_changes_nothing(self) -> None:
        held = in_mode("usr32")
        before = dict(held.spsr)

        held.save(0x12345678)

        self.assertEqual(held.spsr, before)

    def test_writing_one_in_a_privileged_mode_lands_in_that_bank(self) -> None:
        held = in_mode("und32")

        held.save(0x000000DB)

        self.assertEqual(held.spsr["und"], 0x000000DB)


class TheProgramCounterTest(unittest.TestCase):
    def test_reading_it_clears_the_bottom_two_bits(self) -> None:
        held = Registers(seed=1, fill=0)
        held.pc = 0x1006

        counter = held.read(15)

        self.assertEqual(counter, 0x1004)

    def test_writing_it_goes_to_the_counter_rather_than_to_a_bank(self) -> None:
        held = Registers(seed=1, fill=0)

        held.write(15, 0x8000)

        self.assertEqual(held.pc, 0x8000)

    def test_a_value_wider_than_the_bus_is_masked_rather_than_kept(self) -> None:
        held = Registers(seed=1, fill=0)

        held.write(0, 0x1_0000_0001)

        self.assertEqual(held.read(0), 1)


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_register_file_refuses_a_name_it_does_not_have(self) -> None:
        held = Registers(seed=1)

        with self.assertRaises(AttributeError):
            held.q = 1  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main(verbosity=2)

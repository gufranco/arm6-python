"""That the status register is the one ARM60 draws, with ten modes and bit 5 reserved.

Two facts here decide more than they look like they should. ARM60 section 7.4.2
names bit 5 in the reserved list in prose, and on the part the published
conformance corpus was recorded from, bit 5 is the Thumb bit. And section 5.2
says ten modes are reachable in the 32-bit configuration while Table 1 prints
only six, with the other four given by Application Note 11.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import psr  # noqa: E402


class TheBitsTheDatasheetDrawsTest(unittest.TestCase):
    def test_the_condition_flags_sit_at_the_top(self) -> None:
        places = (psr.N_BIT, psr.Z_BIT, psr.C_BIT, psr.V_BIT)

        self.assertEqual(places, (31, 30, 29, 28))

    def test_the_two_interrupt_disables_sit_below_them(self) -> None:
        places = (psr.I_BIT, psr.F_BIT)

        self.assertEqual(places, (7, 6))

    def test_the_mode_field_is_the_bottom_five_bits(self) -> None:
        mask = psr.MODE_MASK

        self.assertEqual(mask, 0b11111)

    def test_the_reserved_bits_are_the_ones_the_datasheet_lists(self) -> None:
        reserved = psr.RESERVED_MASK

        self.assertEqual(reserved, 0x0FFFFF20)

    def test_bit_five_is_reserved_rather_than_a_thumb_bit(self) -> None:
        held = psr.RESERVED_MASK >> 5 & 1

        self.assertEqual(held, 1)

    def test_the_defined_and_the_reserved_bits_between_them_are_the_whole_word(self) -> None:
        covered = psr.DEFINED_MASK | psr.RESERVED_MASK

        self.assertEqual(covered, 0xFFFFFFFF)

    def test_and_no_bit_is_in_both(self) -> None:
        both = psr.DEFINED_MASK & psr.RESERVED_MASK

        self.assertEqual(both, 0)

    def test_eleven_bits_are_defined_as_the_datasheet_says(self) -> None:
        defined = bin(psr.DEFINED_MASK).count("1")

        self.assertEqual(defined, 11)


class TenModesInTwoOverlappingSetsTest(unittest.TestCase):
    def test_there_are_ten_of_them(self) -> None:
        held = len(psr.MODES)

        self.assertEqual(held, 10)

    def test_six_are_the_ones_table_one_prints(self) -> None:
        wide = sorted(one.name for one in psr.MODES.values() if one.wide)

        self.assertEqual(wide, ["abt32", "fiq32", "irq32", "svc32", "und32", "usr32"])

    def test_and_four_are_the_ones_only_the_application_note_prints(self) -> None:
        narrow = sorted(one.name for one in psr.MODES.values() if not one.wide)

        self.assertEqual(narrow, ["fiq26", "irq26", "svc26", "usr26"])

    def test_the_thirty_two_bit_encodings_are_the_ones_table_one_gives(self) -> None:
        held = {one.bits: one.name for one in psr.MODES.values() if one.wide}

        self.assertEqual(
            held,
            {
                0b10000: "usr32",
                0b10001: "fiq32",
                0b10010: "irq32",
                0b10011: "svc32",
                0b10111: "abt32",
                0b11011: "und32",
            },
        )

    def test_the_twenty_six_bit_encodings_are_the_ones_the_application_note_gives(self) -> None:
        held = {one.bits: one.name for one in psr.MODES.values() if not one.wide}

        self.assertEqual(
            held,
            {0b00000: "usr26", 0b00001: "fiq26", 0b00010: "irq26", 0b00011: "svc26"},
        )

    def test_system_mode_is_not_among_them(self) -> None:
        held = psr.mode_for(0b11111)

        self.assertIsNone(held)

    def test_only_the_two_user_modes_are_unprivileged(self) -> None:
        open_to_all = sorted(one.name for one in psr.MODES.values() if not one.privileged)

        self.assertEqual(open_to_all, ["usr26", "usr32"])

    def test_the_two_sets_share_one_bank_per_family(self) -> None:
        held = {psr.MODES["usr26"].bank, psr.MODES["usr32"].bank}

        self.assertEqual(held, {"usr"})

    def test_and_so_do_the_two_fiq_modes(self) -> None:
        held = {psr.MODES["fiq26"].bank, psr.MODES["fiq32"].bank}

        self.assertEqual(held, {"fiq"})

    def test_the_two_modes_with_no_twenty_six_bit_partner_bank_alone(self) -> None:
        held = sorted({psr.MODES["abt32"].bank, psr.MODES["und32"].bank})

        self.assertEqual(held, ["abt", "und"])

    def test_a_user_mode_has_no_saved_status_register(self) -> None:
        held = psr.MODES["usr32"].spsr

        self.assertIsNone(held)

    def test_and_there_are_five_saved_status_registers_in_all(self) -> None:
        held = sorted({one.spsr for one in psr.MODES.values() if one.spsr is not None})

        self.assertEqual(held, ["abt", "fiq", "irq", "svc", "und"])

    def test_a_mode_says_what_it_is_when_printed(self) -> None:
        shown = repr(psr.MODES["svc32"])

        self.assertEqual(shown, "Mode(svc32, bits=0b10011)")


class ReadingAndWritingTheFieldTest(unittest.TestCase):
    def test_the_mode_is_read_out_of_the_bottom_five_bits(self) -> None:
        value = 0xF0000000 | 0b10011

        held = psr.mode_of(value)

        self.assertEqual(held.name, "svc32")

    def test_an_encoding_no_mode_uses_reads_as_nothing(self) -> None:
        held = psr.mode_for(0b10100)

        self.assertIsNone(held)

    def test_reading_an_encoding_no_mode_uses_is_refused_rather_than_guessed(self) -> None:
        with self.assertRaises(psr.UnknownMode):
            psr.mode_of(0b10100)

    def test_and_the_refusal_names_the_encoding_it_was_given(self) -> None:
        with self.assertRaises(psr.UnknownMode) as caught:
            psr.mode_of(0b11111)

        self.assertIn("11111", str(caught.exception))

    def test_writing_a_mode_leaves_every_other_bit_alone(self) -> None:
        value = 0xF00000C0 | 0b10000

        changed = psr.with_mode(value, psr.MODES["fiq32"])

        self.assertEqual(changed, 0xF00000C0 | 0b10001)

    def test_a_flag_is_read_where_the_figure_draws_it(self) -> None:
        value = 1 << psr.C_BIT

        held = (psr.flag(value, psr.N_BIT), psr.flag(value, psr.C_BIT))

        self.assertEqual(held, (False, True))

    def test_a_flag_is_written_where_the_figure_draws_it(self) -> None:
        value = 0

        changed = psr.with_flag(value, psr.V_BIT, True)

        self.assertEqual(changed, 1 << 28)

    def test_and_clearing_one_leaves_the_rest(self) -> None:
        value = 0xF0000000

        changed = psr.with_flag(value, psr.Z_BIT, False)

        self.assertEqual(changed, 0xB0000000)


if __name__ == "__main__":
    unittest.main(verbosity=2)

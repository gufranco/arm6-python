"""That the store is thirty two bits wide, unclean, and endian the way the pin says.

ARM60 drives `a[31:0]`, so the space is four gigabytes and no model can allocate
it. It is held sparsely and everything nobody wrote answers a reproducible
pattern derived from the seed, because a read of a word nothing wrote is a defect
on the board and a store that answers zero turns that defect into a passing test.

`bigend` is a pin rather than a property of the part, so both orders are modelled
and neither is presented as the one the silicon chose.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6.memory import UNSET_SEED, Memory  # noqa: E402


class NothingStartsCleanTest(unittest.TestCase):
    def test_a_word_nobody_wrote_is_not_zero(self) -> None:
        store = Memory()

        held = [store.read_word(address) for address in range(0, 0x400, 4)]

        self.assertNotEqual(set(held), {0})

    def test_the_same_seed_gives_the_same_rubbish_twice(self) -> None:
        first = Memory(seed=1234)
        second = Memory(seed=1234)

        held = [first.read_word(a) == second.read_word(a) for a in range(0, 0x100, 4)]

        self.assertTrue(all(held))

    def test_a_different_seed_gives_different_rubbish(self) -> None:
        first = Memory(seed=1)
        second = Memory(seed=2)

        differ = [first.read_word(a) != second.read_word(a) for a in range(0, 0x400, 4)]

        self.assertIn(True, differ)

    def test_the_default_seed_is_the_one_the_family_uses(self) -> None:
        held = UNSET_SEED

        self.assertEqual(held, 0x5A5A5A5A)

    def test_a_caller_who_asks_for_one_byte_everywhere_gets_it(self) -> None:
        store = Memory(fill=0)

        held = {store.read_word(address) for address in range(0, 0x400, 4)}

        self.assertEqual(held, {0})

    def test_and_the_byte_they_asked_for_rather_than_zero(self) -> None:
        store = Memory(fill=0xEA)

        held = store.read_word(0x100)

        self.assertEqual(held, 0xEAEAEAEA)

    def test_a_word_that_was_written_reads_back(self) -> None:
        store = Memory()

        store.write_word(0x2000, 0xDEADBEEF)

        self.assertEqual(store.read_word(0x2000), 0xDEADBEEF)

    def test_an_image_is_laid_at_the_bottom_where_the_reset_vector_is(self) -> None:
        store = Memory(image=bytes([0x01, 0x02, 0x03, 0x04]))

        held = store.read_word(0)

        self.assertEqual(held, 0x04030201)


class TheWholeThirtyTwoBitSpaceTest(unittest.TestCase):
    def test_the_top_of_the_address_bus_is_reachable(self) -> None:
        store = Memory()

        store.write_word(0xFFFFFFFC, 0x12345678)

        self.assertEqual(store.read_word(0xFFFFFFFC), 0x12345678)

    def test_an_address_past_the_bus_wraps_rather_than_growing(self) -> None:
        store = Memory()

        store.write_word(0x100000000, 0xCAFEBABE)

        self.assertEqual(store.read_word(0), 0xCAFEBABE)

    def test_nothing_is_allocated_for_a_space_nobody_touched(self) -> None:
        store = Memory()

        store.write_word(0x80000000, 1)

        self.assertLess(len(store.written), 16)


class TheAddressLinesAWordAccessIgnoresTest(unittest.TestCase):
    def test_a_word_access_is_taken_from_the_aligned_address(self) -> None:
        store = Memory(fill=0)
        store.write_word(0x1000, 0x11223344)

        held = store.read_word(0x1002)

        self.assertEqual(held, 0x11223344)

    def test_and_a_word_write_lands_on_the_aligned_address(self) -> None:
        store = Memory(fill=0)

        store.write_word(0x1003, 0x55667788)

        self.assertEqual(store.read_word(0x1000), 0x55667788)


class WhichEndTheBoardPutsFirstTest(unittest.TestCase):
    def test_little_endian_puts_the_lowest_byte_at_the_lowest_address(self) -> None:
        store = Memory(fill=0)

        store.write_word(0x40, 0xAABBCCDD)

        self.assertEqual(store.read_byte(0x40), 0xDD)

    def test_big_endian_puts_the_highest_byte_there(self) -> None:
        store = Memory(fill=0, bigend=True)

        store.write_word(0x40, 0xAABBCCDD)

        self.assertEqual(store.read_byte(0x40), 0xAA)

    def test_a_byte_written_shows_in_the_word_that_holds_it(self) -> None:
        store = Memory(fill=0)

        store.write_byte(0x41, 0x99)

        self.assertEqual(store.read_word(0x40), 0x00009900)

    def test_and_at_the_other_end_when_the_pin_is_high(self) -> None:
        store = Memory(fill=0, bigend=True)

        store.write_byte(0x41, 0x99)

        self.assertEqual(store.read_word(0x40), 0x00990000)

    def test_a_byte_read_takes_the_addressed_byte_whatever_the_order(self) -> None:
        store = Memory(fill=0)
        store.write_word(0x50, 0x01020304)

        held = [store.read_byte(0x50 + one) for one in range(4)]

        self.assertEqual(held, [0x04, 0x03, 0x02, 0x01])


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_store_refuses_a_name_it_does_not_have(self) -> None:
        store = Memory()

        with self.assertRaises(AttributeError):
            store.q = 1  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main(verbosity=2)

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import UNSET_SEED, Memory  # noqa: E402
from conformance.printed import value  # noqa: E402


class NothingStartsCleanTest(unittest.TestCase):
    def test_a_word_nobody_wrote_is_not_zero(self) -> None:
        # Arrange
        store = Memory()

        # Act
        held = [store.read_word(address) for address in range(0, 0x400, 4)]

        # Assert
        self.assertNotEqual(set(held), {0})

    def test_the_same_seed_gives_the_same_rubbish_twice(self) -> None:
        # Arrange
        first = Memory(seed=1234)
        second = Memory(seed=1234)

        # Act
        held = [first.read_word(a) == second.read_word(a) for a in range(0, 0x100, 4)]

        # Assert
        self.assertEqual(set(held), {True})

    def test_a_different_seed_gives_different_rubbish(self) -> None:
        # Arrange
        first = Memory(seed=1)
        second = Memory(seed=2)

        # Act
        differ = [first.read_word(a) != second.read_word(a) for a in range(0, 0x400, 4)]

        # Assert
        self.assertIn(True, differ)

    def test_the_default_seed_is_the_one_the_family_uses(self) -> None:
        # Arrange
        unseeded = Memory()

        # Act
        held = [unseeded.read_byte(a) for a in range(0x100)]

        # Assert
        self.assertEqual(
            (held, UNSET_SEED),
            ([Memory(seed=0x5A5A5A5A).read_byte(a) for a in range(0x100)], 0x5A5A5A5A),
        )

    def test_a_caller_who_asks_for_one_byte_everywhere_gets_it(self) -> None:
        # Arrange
        store = Memory(fill=0)

        # Act
        held = {store.read_word(address) for address in range(0, 0x400, 4)}

        # Assert
        self.assertEqual(held, {0})

    def test_and_the_byte_they_asked_for_rather_than_zero(self) -> None:
        # Arrange
        store = Memory(fill=0xEA)

        # Act
        held = store.read_word(0x100)

        # Assert
        self.assertEqual(held, 0xEAEAEAEA)

    def test_a_word_that_was_written_reads_back(self) -> None:
        # Arrange
        store = Memory()

        # Act
        store.write_word(0x2000, 0xDEADBEEF)

        # Assert
        self.assertEqual(store.read_word(0x2000), 0xDEADBEEF)

    def test_an_image_is_laid_at_the_bottom_where_the_reset_vector_is(self) -> None:
        # Arrange
        image = bytes([0x01, 0x02, 0x03, 0x04])

        # Act
        store = Memory(image=image)

        # Assert
        self.assertEqual(store.read_word(0), 0x04030201)


class TheWholeThirtyTwoBitSpaceTest(unittest.TestCase):
    def test_the_top_of_the_address_bus_is_reachable(self) -> None:
        # Arrange
        store = Memory()
        top = (1 << value("addressBus")) - 4

        # Act
        store.write_word(top, 0x12345678)

        # Assert
        self.assertEqual(
            (store.read_word(top), max(store.written) + 1),
            (0x12345678, 1 << value("addressBus")),
        )

    def test_an_address_past_the_bus_wraps_rather_than_growing(self) -> None:
        # Arrange
        store = Memory()

        # Act
        store.write_word(0x100000000, 0xCAFEBABE)

        # Assert
        self.assertEqual(store.read_word(0), 0xCAFEBABE)

    def test_nothing_is_allocated_for_a_space_nobody_touched(self) -> None:
        # Arrange
        store = Memory()

        # Act
        store.write_word(0x80000000, 1)

        # Assert
        self.assertEqual(sorted(store.written), [0x80000000, 0x80000001, 0x80000002, 0x80000003])


class TheAddressLinesAWordAccessIgnoresTest(unittest.TestCase):
    def test_a_word_access_is_taken_from_the_aligned_address(self) -> None:
        # Arrange
        store = Memory(fill=0)
        store.write_word(0x1000, 0x11223344)

        # Act
        held = store.read_word(0x1002)

        # Assert
        self.assertEqual(held, 0x11223344)

    def test_and_a_word_write_lands_on_the_aligned_address(self) -> None:
        # Arrange
        store = Memory(fill=0)

        # Act
        store.write_word(0x1003, 0x55667788)

        # Assert
        self.assertEqual(store.read_word(0x1000), 0x55667788)


class WhichEndTheBoardPutsFirstTest(unittest.TestCase):
    def test_little_endian_puts_the_lowest_byte_at_the_lowest_address(self) -> None:
        # Arrange
        store = Memory(fill=0)

        # Act
        store.write_word(0x40, 0xAABBCCDD)

        # Assert
        self.assertEqual(store.read_byte(0x40), 0xDD)

    def test_big_endian_puts_the_highest_byte_there(self) -> None:
        # Arrange
        store = Memory(fill=0, bigend=True)

        # Act
        store.write_word(0x40, 0xAABBCCDD)

        # Assert
        self.assertEqual(store.read_byte(0x40), 0xAA)

    def test_a_byte_written_shows_in_the_word_that_holds_it(self) -> None:
        # Arrange
        store = Memory(fill=0)

        # Act
        store.write_byte(0x41, 0x99)

        # Assert
        self.assertEqual(store.read_word(0x40), 0x00009900)

    def test_and_at_the_other_end_when_the_pin_is_high(self) -> None:
        # Arrange
        store = Memory(fill=0, bigend=True)

        # Act
        store.write_byte(0x41, 0x99)

        # Assert
        self.assertEqual(store.read_word(0x40), 0x00990000)

    def test_a_byte_read_takes_the_addressed_byte_whatever_the_order(self) -> None:
        # Arrange
        store = Memory(fill=0)
        store.write_word(0x50, 0x01020304)

        # Act
        held = [store.read_byte(0x50 + one) for one in range(4)]

        # Assert
        self.assertEqual(held, [0x04, 0x03, 0x02, 0x01])


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_store_refuses_a_name_it_does_not_have(self) -> None:
        # Arrange
        store = Memory()

        # Act
        with self.assertRaises(AttributeError) as caught:
            store.q = 1  # type: ignore[attr-defined]

        # Assert
        self.assertIn("q", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

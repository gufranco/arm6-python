"""That a part can be stopped between any two cycles, not only between instructions.

`step` runs a whole instruction because that is the unit a program is written in.
A board has no such unit: it has a clock, and between two edges of it a memory
system can change what a read will answer. Reaching that needs the part suspended
part way through an instruction, which is what this class is for and what makes
it much slower than `step`.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6.clock import Clock  # noqa: E402
from arm6.core import Cpu  # noqa: E402
from arm6.errors import ClockClosed  # noqa: E402
from arm6.memory import Memory  # noqa: E402

MOVE = 0xE1A00001
BRANCH_WITH_LINK = 0xEB000000


def machine(*words: int) -> Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


class OneCycleAtATimeTest(unittest.TestCase):
    def test_a_tick_advances_exactly_one_cycle(self) -> None:
        with Clock(machine(*([MOVE] * 8))) as clock:
            spent = clock.tick()

            self.assertEqual(spent, 1)

    def test_a_budget_stops_in_the_middle_of_an_instruction(self) -> None:
        held = machine(BRANCH_WITH_LINK, *([MOVE] * 8))

        with Clock(held) as clock:
            clock.run_for(2)

            self.assertEqual(clock.cycles, 2)

    def test_which_is_something_the_part_s_own_budget_cannot_do(self) -> None:
        held = machine(BRANCH_WITH_LINK, *([MOVE] * 8))

        spent = held.run_for(2)

        self.assertEqual(spent, 3)

    def test_a_clock_can_be_iterated_a_cycle_at_a_time(self) -> None:
        with Clock(machine(*([MOVE] * 8))) as clock:
            seen = [next(clock) for _ in range(4)]

            self.assertEqual(seen, [1, 2, 3, 4])

    def test_the_running_total_is_what_a_tick_reports(self) -> None:
        with Clock(machine(*([MOVE] * 8))) as clock:
            clock.run_for(3)

            self.assertEqual(clock.cycles, 3)


class ClosingItTest(unittest.TestCase):
    def test_a_closed_clock_refuses_another_tick(self) -> None:
        clock = Clock(machine(*([MOVE] * 8)))
        clock.close()

        with self.assertRaises(ClockClosed):
            clock.tick()

    def test_closing_it_twice_is_not_an_error(self) -> None:
        clock = Clock(machine(*([MOVE] * 8)))
        clock.close()

        clock.close()

        self.assertTrue(clock.closed)

    def test_it_gives_the_part_its_watcher_back(self) -> None:
        held = machine(*([MOVE] * 8))
        clock = Clock(held)

        clock.close()

        self.assertIsNone(held.on_cycle)

    def test_a_closed_clock_stops_an_iteration_rather_than_raising(self) -> None:
        clock = Clock(machine(*([MOVE] * 8)))
        clock.close()

        held = list(clock)

        self.assertEqual(held, [])


class AFailureInsideTheWorkerReachesTheDriverTest(unittest.TestCase):
    def test_an_encoding_the_part_refuses_is_raised_to_the_caller(self) -> None:
        from arm6.transfers import UnspecifiedEncoding

        with Clock(machine(0xE0812394)) as clock, self.assertRaises(UnspecifiedEncoding):
            clock.run_for(8)

    def test_and_the_clock_closes_itself_rather_than_being_left_running(self) -> None:
        from arm6.transfers import UnspecifiedEncoding

        clock = Clock(machine(0xE0812394))
        with self.assertRaises(UnspecifiedEncoding):
            clock.run_for(8)

        self.assertTrue(clock.closed)


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_clock_refuses_a_name_it_does_not_have(self) -> None:
        with Clock(machine(*([MOVE] * 8))) as clock, self.assertRaises(AttributeError):
            clock.q = 1  # type: ignore[attr-defined]


if __name__ == "__main__":
    unittest.main(verbosity=2)

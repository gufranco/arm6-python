from __future__ import annotations

import sys
import threading
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import Clock, ClockClosed, Cpu, Memory, UnspecifiedEncoding  # noqa: E402

MOVE = 0xE1A00001
BRANCH_WITH_LINK = 0xEB000000
LONG_MULTIPLY = 0xE0812394
EVERY_KIND_OF_ACCESS = (
    0xE3A0002A,
    0xE2801001,
    0xE3A02C01,
    0xE5821000,
    0xE5923000,
    0xE5C20008,
    0xE5D29008,
    0xE8A20003,
    0xE9320030,
    0xE1026090,
    0xE0070190,
    0xEB000000,
    0xE1A00000,
    0xE1A08011,
)

INSTRUCTIONS = 4

BUDGET = 4

PATIENCE_SECONDS = 10.0


def machine(*words: int) -> Cpu:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    held = Cpu("arm60", Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


def stepped(instructions: int) -> tuple[int, int]:
    held = machine(*([MOVE] * 8))
    for _ in range(instructions):
        held.step()
    return held.steps, held.cycles


def within(call: Callable[[], Any]) -> tuple[str, Any]:
    outcome: list[tuple[str, Any]] = []

    def attempt() -> None:
        try:
            outcome.append(("returned", call()))
        except Exception as raised:  # noqa: BLE001
            outcome.append(("raised", raised))

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(PATIENCE_SECONDS)
    return outcome[0] if outcome else ("still running", None)


def clocked_then_closed(budget: int) -> tuple[int, int]:
    held = machine(*([MOVE] * 8))
    with Clock(held) as clock:
        clock.run_for(budget)
    return held.steps, held.cycles


def observed(held: Cpu) -> tuple[Any, ...]:
    return (
        held.registers.pc,
        tuple(held.registers.read(index) for index in range(15)),
        held.registers.cpsr,
        held.steps,
        held.cycles,
        held.spent,
        held.tally,
        tuple(repr(one) for one in held.bus.cycles),
        dict(held.memory.written),
    )


def after_steps(words: tuple[int, ...], instructions: int) -> tuple[int, tuple[Any, ...]]:
    held = machine(*words)
    spent = sum(held.step() for _ in range(instructions))
    return spent, observed(held)


def after_ticks(words: tuple[int, ...], budget: int, closing: bool) -> tuple[Any, ...]:
    held = machine(*words)
    clock = Clock(held)
    try:
        clock.run_for(budget)
        if closing:
            clock.close()
        return observed(held)
    finally:
        clock.close()


class OneCycleAtATimeTest(unittest.TestCase):
    def test_a_tick_advances_exactly_one_cycle(self) -> None:
        # Arrange
        clock = Clock(machine(*([MOVE] * 8)))
        self.addCleanup(clock.close)

        # Act
        spent = clock.tick()

        # Assert
        self.assertEqual((spent, clock.cpu.cycles), (1, 1))

    def test_a_budget_stops_in_the_middle_of_an_instruction(self) -> None:
        # Arrange
        held = machine(BRANCH_WITH_LINK, *([MOVE] * 8))
        clock = Clock(held)
        self.addCleanup(clock.close)

        # Act
        clock.run_for(2)

        # Assert
        self.assertEqual((clock.cycles, held.registers.pc, len(held.bus.cycles)), (2, 8, 2))

    def test_which_is_something_the_part_s_own_budget_cannot_do(self) -> None:
        # Arrange
        held = machine(BRANCH_WITH_LINK, *([MOVE] * 8))

        # Act
        spent = held.run_for(2)

        # Assert
        self.assertEqual(spent, 3)

    def test_a_clock_can_be_iterated_a_cycle_at_a_time(self) -> None:
        # Arrange
        clock = Clock(machine(*([MOVE] * 8)))
        self.addCleanup(clock.close)

        # Act
        seen = [next(clock) for _ in range(4)]

        # Assert
        self.assertEqual(seen, [1, 2, 3, 4])

    def test_the_running_total_is_what_a_tick_reports(self) -> None:
        # Arrange
        clock = Clock(machine(*([MOVE] * 8)))
        self.addCleanup(clock.close)

        # Act
        reported = clock.run_for(3)

        # Assert
        self.assertEqual((reported, clock.cycles), (3, 3))

    def test_a_with_block_closes_the_clock_it_opened(self) -> None:
        # Arrange
        held = machine(*([MOVE] * 8))

        # Act
        with Clock(held) as clock:
            clock.tick()

        # Assert
        self.assertEqual((clock.closed, held.on_cycle), (True, None))


class ClosingItTest(unittest.TestCase):
    def test_a_closed_clock_refuses_another_tick(self) -> None:
        # Arrange
        clock = Clock(machine(*([MOVE] * 8)))
        clock.close()

        # Act
        kind, raised = within(clock.tick)

        # Assert
        self.assertEqual(
            (kind, type(raised), str(raised)),
            ("raised", ClockClosed, "this clock has been closed"),
        )

    def test_closing_it_twice_is_not_an_error(self) -> None:
        # Arrange
        clock = Clock(machine(*([MOVE] * 8)))
        clock.close()

        # Act
        clock.close()

        # Assert
        self.assertTrue(clock.closed)

    def test_it_gives_the_part_its_watcher_back(self) -> None:
        # Arrange
        held = machine(*([MOVE] * 8))
        clock = Clock(held)

        # Act
        clock.close()

        # Assert
        self.assertIsNone(held.on_cycle)

    def test_a_closed_clock_stops_an_iteration_rather_than_raising(self) -> None:
        # Arrange
        clock = Clock(machine(*([MOVE] * 8)))
        clock.close()

        # Act
        held = within(lambda: list(clock))

        # Assert
        self.assertEqual(held, ("returned", []))


class CountedLikeAStepTest(unittest.TestCase):
    def test_a_clock_counts_the_same_instructions_and_cycles_as_stepping(self) -> None:
        # Arrange
        held = machine(*([MOVE] * 8))
        clock = Clock(held)
        self.addCleanup(clock.close)

        # Act
        clock.run_for(BUDGET)

        # Assert
        self.assertEqual(
            ((held.steps, held.cycles), stepped(INSTRUCTIONS)),
            ((4, 4), (4, 4)),
        )

    def test_and_still_does_once_the_clock_is_closed(self) -> None:
        # Arrange
        expected = stepped(INSTRUCTIONS)

        # Act
        found = within(lambda: clocked_then_closed(BUDGET))

        # Assert
        self.assertEqual((found, expected), (("returned", (4, 4)), (4, 4)))


class TheLastCycleOfAnInstructionFinishesItTest(unittest.TestCase):
    def test_a_clock_leaves_the_state_the_same_steps_leave(self) -> None:
        # Arrange
        budget, expected = after_steps((MOVE,) * 8, INSTRUCTIONS)

        # Act
        found = within(lambda: after_ticks((MOVE,) * 8, budget, closing=False))

        # Assert
        self.assertEqual(found, ("returned", expected))

    def test_and_so_does_a_clock_closed_on_that_cycle(self) -> None:
        # Arrange
        budget, expected = after_steps((MOVE,) * 8, INSTRUCTIONS)

        # Act
        found = within(lambda: after_ticks((MOVE,) * 8, budget, closing=True))

        # Assert
        self.assertEqual(found, ("returned", expected))

    def test_through_loads_stores_a_swap_a_multiply_and_a_branch(self) -> None:
        # Arrange
        budget, expected = after_steps(EVERY_KIND_OF_ACCESS, len(EVERY_KIND_OF_ACCESS))

        # Act
        found = within(lambda: after_ticks(EVERY_KIND_OF_ACCESS, budget, closing=False))

        # Assert
        self.assertEqual(found, ("returned", expected))

    def test_and_through_them_once_the_clock_is_closed(self) -> None:
        # Arrange
        budget, expected = after_steps(EVERY_KIND_OF_ACCESS, len(EVERY_KIND_OF_ACCESS))

        # Act
        found = within(lambda: after_ticks(EVERY_KIND_OF_ACCESS, budget, closing=True))

        # Assert
        self.assertEqual(found, ("returned", expected))


class Watched:
    __slots__ = ("held", "inner", "paused", "seen")

    def __init__(self, inner: Memory) -> None:
        self.inner = inner
        self.held: list[Cpu] = []
        self.paused = 0
        self.seen: list[tuple[int, int]] = []

    def noted(self, address: int) -> int:
        for part in self.held:
            self.seen.append((self.paused, part.tally.total + len(part.bus.cycles)))
        return address

    def read_byte(self, address: int) -> int:
        return self.inner.read_byte(self.noted(address))

    def read_word(self, address: int) -> int:
        return self.inner.read_word(self.noted(address))

    def write_byte(self, address: int, value: int) -> None:
        self.inner.write_byte(self.noted(address), value)

    def write_word(self, address: int, value: int) -> None:
        self.inner.write_word(self.noted(address), value)


def watched_run(words: tuple[int, ...]) -> list[tuple[int, int]]:
    image = b"".join(one.to_bytes(4, "little") for one in words)
    memory = Watched(Memory(image=image, fill=0))
    held = Cpu("arm60", memory, fill=0)  # type: ignore[arg-type]
    held.registers.pc = 0
    memory.held.append(held)

    def paused(part: Cpu) -> None:
        memory.paused += 1

    held.on_cycle = paused
    for _ in words:
        held.step()
    return memory.seen


class EveryAccessStaysOnItsOwnCycleTest(unittest.TestCase):
    def test_no_access_is_made_before_the_cycle_ahead_of_it_has_paused(self) -> None:
        # Arrange
        words = EVERY_KIND_OF_ACCESS

        # Act
        seen = watched_run(words)

        # Assert
        self.assertEqual([paused for paused, _ in seen], [due for _, due in seen])


class AFailureInsideTheWorkerReachesTheDriverTest(unittest.TestCase):
    def test_an_encoding_the_part_refuses_is_raised_to_the_caller(self) -> None:
        # Arrange
        clock = Clock(machine(LONG_MULTIPLY))
        self.addCleanup(clock.close)

        # Act
        with self.assertRaises(UnspecifiedEncoding) as caught:
            clock.run_for(8)

        # Assert
        self.assertIn("0xE0812394", str(caught.exception))

    def test_and_the_clock_closes_itself_rather_than_being_left_running(self) -> None:
        # Arrange
        clock = Clock(machine(LONG_MULTIPLY))

        # Act
        with self.assertRaises(UnspecifiedEncoding):
            clock.run_for(8)

        # Assert
        self.assertTrue(clock.closed)


class NothingHereKeepsADictionaryTest(unittest.TestCase):
    def test_the_clock_refuses_a_name_it_does_not_have(self) -> None:
        # Arrange
        clock = Clock(machine(*([MOVE] * 8)))
        self.addCleanup(clock.close)

        # Act
        with self.assertRaises(AttributeError) as caught:
            clock.q = 1  # type: ignore[attr-defined]

        # Assert
        self.assertIn("q", str(caught.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)

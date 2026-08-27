"""That the measuring measures, driven by a clock the test controls.

The floor itself is not asserted here. This file runs under a coverage tracer,
and the tracer costs about ten times what the model does, so a throughput
assertion in this environment measures the tracer rather than the model. What is
checked here is the arithmetic, the reporting and the exit codes, with a fake
clock so the numbers are known rather than measured.
"""

from __future__ import annotations

import sys
import unittest
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import speed  # noqa: E402


def ticking(*seconds: float) -> Callable[[], float]:
    """A clock that hands out a fixed sequence, so a rate is arithmetic."""
    marks = iter(seconds)

    def clock() -> float:
        return next(marks)

    return clock


class WhatARunMeasuredTest(unittest.TestCase):
    def test_the_median_is_taken_rather_than_the_mean(self) -> None:
        held = speed.Timed("arm60", 100, (1.0, 2.0, 30.0))

        self.assertEqual(held.median, 2.0)

    def test_the_rate_is_cycles_over_the_median(self) -> None:
        held = speed.Timed("arm60", 100, (1.0, 2.0, 30.0))

        self.assertEqual(held.rate, 50.0)

    def test_the_share_of_real_time_is_against_the_provisional_clock(self) -> None:
        held = speed.Timed("arm60", speed.PART_HERTZ, (1.0,))

        self.assertEqual(held.of_real_time, 1.0)

    def test_a_run_above_the_floor_beats_it(self) -> None:
        held = speed.Timed("arm60", 1_000_000, (1.0,))

        self.assertTrue(held.beats(500_000))

    def test_and_one_below_it_does_not(self) -> None:
        held = speed.Timed("arm60", 1_000, (1.0,))

        self.assertFalse(held.beats(500_000))

    def test_a_run_says_what_it_measured_when_printed(self) -> None:
        held = repr(speed.Timed("arm60", 100, (1.0,)))

        self.assertIn("cycles per second", held)


class TheRunItselfTest(unittest.TestCase):
    def test_it_runs_once_per_repeat(self) -> None:
        held = speed.timed(cycles=64, repeats=3, clock=ticking(0.0, 1.0, 0.0, 1.0, 0.0, 1.0))

        self.assertEqual(len(held.seconds), 3)

    def test_and_reports_the_part_it_drove(self) -> None:
        held = speed.timed(cycles=64, repeats=1, clock=ticking(0.0, 1.0))

        self.assertEqual(held.part, "arm60")

    def test_the_part_it_builds_is_pointed_at_something_it_can_run(self) -> None:
        held = speed.build()

        spent = held.step()

        self.assertEqual(spent, 1)

    def test_and_that_part_starts_at_the_bottom_of_the_store(self) -> None:
        held = speed.build()

        self.assertEqual(held.registers.pc, 0)


class WhatItPrintsTest(unittest.TestCase):
    def test_a_run_above_the_floor_says_what_it_managed(self) -> None:
        held = speed.lines_for(speed.Timed("arm60", 1_000_000, (1.0,)), floor=1)

        self.assertIn("cycles per second at the median", held[0])

    def test_a_run_below_it_says_so_outright(self) -> None:
        held = speed.lines_for(speed.Timed("arm60", 1, (1.0,)), floor=500_000)

        self.assertIn("below the floor", "\n".join(held))

    def test_and_a_run_above_it_does_not(self) -> None:
        held = speed.lines_for(speed.Timed("arm60", 1_000_000, (1.0,)), floor=1)

        self.assertNotIn("below the floor", "\n".join(held))

    def test_the_runtime_version_is_printed_beside_the_number(self) -> None:
        held = speed.lines_for(speed.Timed("arm60", 100, (1.0,)), floor=1)

        self.assertIn("on Python", "\n".join(held))

    def test_the_comparison_says_the_figure_it_compares_against_is_provisional(self) -> None:
        held = speed.lines_for(speed.Timed("arm60", 100, (1.0,)), floor=1)

        self.assertIn("provisional", "\n".join(held))


class TheCommandLineTest(unittest.TestCase):
    def test_no_options_gives_the_defaults(self) -> None:
        held = speed.options([])

        self.assertEqual(held, (speed.CYCLES, speed.REPEATS))

    def test_the_cycle_count_can_be_set(self) -> None:
        held = speed.options(["--cycles", "10"])

        self.assertEqual(held[0], 10)

    def test_the_repeat_count_can_be_set(self) -> None:
        held = speed.options(["--repeats", "3"])

        self.assertEqual(held[1], 3)

    def test_an_option_nobody_offers_is_refused(self) -> None:
        with self.assertRaises(speed.Usage):
            speed.options(["--fast"])

    def test_an_option_with_no_value_is_refused_too(self) -> None:
        with self.assertRaises(speed.Usage):
            speed.options(["--cycles"])


class TheExitCodeTest(unittest.TestCase):
    def test_a_run_that_beats_the_floor_exits_zero(self) -> None:
        held = speed.main(
            [],
            floor=1,
            run=lambda **_: speed.Timed("arm60", 1_000_000, (1.0,)),
            say=lambda _: None,
        )

        self.assertEqual(held, 0)

    def test_a_run_that_does_not_exits_one(self) -> None:
        held = speed.main(
            [],
            floor=10**9,
            run=lambda **_: speed.Timed("arm60", 1, (1.0,)),
            say=lambda _: None,
        )

        self.assertEqual(held, 1)

    def test_a_bad_option_exits_two_and_says_why(self) -> None:
        said: list[str] = []

        held = speed.main(["--fast"], say=said.append)

        self.assertEqual((held, "unknown option --fast" in said), (2, True))

    def test_the_report_is_printed_rather_than_kept(self) -> None:
        said: list[str] = []

        speed.main(
            [],
            floor=1,
            run=lambda **_: speed.Timed("arm60", 100, (1.0,)),
            say=said.append,
        )

        self.assertGreater(len(said), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""How fast the model runs, and a floor it must not fall through.

Not a benchmark for its own sake. A model of a processor is only useful if it can
be driven for long enough to be interesting, and the way that stops being true is
gradual: a helper grows an allocation, a property becomes a lookup, and a year
later nothing can be swept. A floor that fails loudly is cheaper than noticing.

The floor is deliberately far below what the model does today. It is there to
catch something several times slower, not to police the noise between one runner
and another, because a shared runner's variance is larger than any change worth
arguing about.

Every figure is a median across repeats rather than a mean, because one scheduling
hiccup moves a mean and moves a median much less, and the runtime version is
printed beside it because it is the single thing that changes these numbers most.

The rate is reported in cycles per second rather than instructions per second,
because this part does not take one cycle per instruction and the thing a host
paces against is the cycle. The comparison against the silicon is drawn against a
provisional figure and says so: chapter 12 of the datasheet opens by calling its
AC parameters preliminary, and the clock rate below is derived from them.

The floor is checked here and never from inside the test suite, because the suite
runs under a coverage tracer and the tracer costs about ten times what the model
does. A throughput assertion in that environment measures the tracer. So the tests
beside this file check the measuring, with a clock they control, and the
measurement itself is a step of its own.

Usage:
    python3 -m conformance.speed [--repeats N] [--cycles N]
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, override

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from arm6.core import Cpu
from arm6.memory import Memory

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Sequence

CYCLES = 200_000
"""How many cycles one repeat runs. Long enough to swamp the setup."""

REPEATS = 7
"""How many repeats a median is taken over. Odd, so the median is a measurement."""

FLOOR = 100_000
"""Cycles per second the model must beat, uninstrumented.

Measured at 387,727 cycles per second on Python 3.14 when this was written, so
the floor sits close to four times below it. That leaves room for a shared runner
having a bad minute and none for a change that made the model several times
slower.
"""

PART_HERTZ = 20_000_000
"""The rate the datasheet's own AC parameters imply, and a provisional one.

Chapter 12 gives `Tckl` and `Tckh` a minimum of 25 ns each, so the shortest `mclk`
period this grade allows is 50 ns and the part tops out near 20 MHz. That chapter
opens by calling its figures preliminary data subject to change when device
characterisation is complete, so the ratio below is a comparison against a
provisional number and is printed as one.
"""

EXERCISE = 0xE1A00001
"""`MOV R0, R1`, which costs one sequential cycle and touches nothing else.

A field of one instruction is what a throughput floor wants: it measures the
model rather than whichever mix of instructions a program happened to contain.
"""


class Usage(Exception):
    pass


class Timed:
    """What a run measured."""

    def __init__(self, part: str, cycles: int, seconds: Sequence[float]) -> None:
        self.part = part
        self.cycles = cycles
        self.seconds = tuple(seconds)

    @property
    def median(self) -> float:
        return statistics.median(self.seconds)

    @property
    def rate(self) -> float:
        """Cycles per second, at the median."""
        return self.cycles / self.median

    @property
    def of_real_time(self) -> float:
        """What fraction of the silicon's own rate this manages."""
        return self.rate / PART_HERTZ

    def beats(self, floor: int) -> bool:
        return self.rate >= floor

    @override
    def __repr__(self) -> str:
        return f"<Timed {self.part}, {self.rate:,.0f} cycles per second>"


def _clock() -> float:  # pragma: no cover
    return time.perf_counter()


def build(part: str = "arm60") -> Cpu:
    """A part pointed at a field of one instruction, with nothing else in the way."""
    image = EXERCISE.to_bytes(4, "little") * 4096
    held = Cpu(part, Memory(image=image, fill=0), fill=0)
    held.registers.pc = 0
    return held


def timed(
    part: str = "arm60",
    cycles: int = CYCLES,
    repeats: int = REPEATS,
    clock: Callable[[], float] = _clock,
) -> Timed:
    """Run that many cycles that many times, from a fresh part each repeat."""
    seconds = []
    for _ in range(repeats):
        held = build(part)
        at = clock()
        held.run_for(cycles)
        seconds.append(clock() - at)
    return Timed(part, cycles, seconds)


def lines_for(found: Timed, floor: int = FLOOR) -> list[str]:
    """What was measured, with the numbers a reader needs to judge it."""
    said = [
        f"  {found.part}: {found.rate:,.0f} cycles per second at the median"
        f" of {len(found.seconds)} runs of {found.cycles:,}",
        f"     median {found.median:.3f}s, fastest {min(found.seconds):.3f}s,"
        f" slowest {max(found.seconds):.3f}s",
        f"     {found.of_real_time * 100:.1f}% of the {PART_HERTZ:,} cycles per second"
        " the datasheet's provisional AC parameters imply",
        f"     on Python {sys.version.split()[0]}",
    ]
    if not found.beats(floor):
        said.append(
            f"  ! below the floor of {floor:,} cycles per second."
            " Something got several times slower rather than a little noisier"
        )
    return said


def options(argv: Sequence[str]) -> tuple[int, int]:
    """How many cycles and how many repeats, from the command line."""
    cycles = CYCLES
    repeats = REPEATS
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item not in ("--cycles", "--repeats"):
            raise Usage(f"unknown option {item}")
        if not rest:
            raise Usage(f"{item} needs a value")
        if item == "--cycles":
            cycles = int(rest.pop(0))
        else:
            repeats = int(rest.pop(0))
    return cycles, repeats


def main(
    argv: Sequence[str],
    floor: int = FLOOR,
    run: Callable[..., Timed] = timed,
    say: Callable[[str], object] = print,
) -> int:
    try:
        cycles, repeats = options(argv)
    except Usage as error:
        say(str(error))
        return 2

    found = run(cycles=cycles, repeats=repeats)
    for line in lines_for(found, floor):
        say(line)
    return 0 if found.beats(floor) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

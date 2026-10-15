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

REPEATS = 7

SHARED_RUNNER_RATE = 150_445

RUNNER_HEADROOM = 3

FLOOR_STEP = 10_000

FLOOR = SHARED_RUNNER_RATE // RUNNER_HEADROOM // FLOOR_STEP * FLOOR_STEP

PRELIMINARY_TCKL_MIN_NS = 25

PRELIMINARY_TCKH_MIN_NS = 25

NANOSECONDS_PER_SECOND = 1_000_000_000

PART_HERTZ = NANOSECONDS_PER_SECOND // (PRELIMINARY_TCKL_MIN_NS + PRELIMINARY_TCKH_MIN_NS)

EXERCISE = 0xE1A00001


class Usage(Exception):
    pass


class Timed:
    def __init__(self, part: str, cycles: int, seconds: Sequence[float]) -> None:
        self.part = part
        self.cycles = cycles
        self.seconds = tuple(seconds)

    @property
    def median(self) -> float:
        return statistics.median(self.seconds)

    @property
    def rate(self) -> float:
        return self.cycles / self.median

    @property
    def of_real_time(self) -> float:
        return self.rate / PART_HERTZ

    def beats(self, floor: int) -> bool:
        return self.rate >= floor

    @override
    def __repr__(self) -> str:
        return f"<Timed {self.part}, {self.rate:,.0f} cycles per second>"


def _clock() -> float:  # pragma: no cover
    return time.perf_counter()


def build(part: str = "arm60") -> Cpu:
    image = EXERCISE.to_bytes(4, "little") * 4096
    held: Cpu = Cpu(part, Memory(image=image, fill=0), fill=0).reset()
    return held


def timed(
    part: str = "arm60",
    cycles: int = CYCLES,
    repeats: int = REPEATS,
    clock: Callable[[], float] = _clock,
) -> Timed:
    seconds = []
    for _ in range(repeats):
        held = build(part)
        at = clock()
        held.run_for(cycles)
        seconds.append(clock() - at)
    return Timed(part, cycles, seconds)


def lines_for(found: Timed, floor: int = FLOOR) -> list[str]:
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

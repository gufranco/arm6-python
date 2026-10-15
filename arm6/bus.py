from __future__ import annotations

from typing import override

from arm6.tally import Cycles


class CycleType:
    __slots__ = ("letter", "name", "nmreq", "seq")

    letter: str
    name: str
    nmreq: int
    seq: int

    def __init__(self, letter: str, name: str, nmreq: int, seq: int) -> None:
        object.__setattr__(self, "letter", letter)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "nmreq", nmreq)
        object.__setattr__(self, "seq", seq)

    @override
    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("a cycle type is a row of Table 3 and does not change")

    @property
    def touches_memory(self) -> bool:
        return self.nmreq == 0

    @override
    def __repr__(self) -> str:
        return f"CycleType({self.letter})"


NONSEQUENTIAL = CycleType("N", "non-sequential", nmreq=0, seq=0)
SEQUENTIAL = CycleType("S", "sequential", nmreq=0, seq=1)
INTERNAL = CycleType("I", "internal", nmreq=1, seq=0)
COPROCESSOR = CycleType("C", "coprocessor register transfer", nmreq=1, seq=1)

TYPES = (NONSEQUENTIAL, SEQUENTIAL, INTERNAL, COPROCESSOR)


class Cycle:
    __slots__ = ("address", "data", "kind", "lock", "nbw", "nopc", "nrw", "ntrans")

    kind: CycleType
    address: int
    nopc: int
    nbw: int
    nrw: int
    ntrans: int
    lock: int
    data: int | None

    def __init__(
        self,
        kind: CycleType,
        address: int,
        nopc: int,
        nbw: int = 1,
        nrw: int = 0,
        ntrans: int = 1,
        lock: int = 0,
        data: int | None = None,
    ) -> None:
        self.kind = kind
        self.address = address & 0xFFFFFFFF
        self.nopc = nopc
        self.nbw = nbw
        self.nrw = nrw
        self.ntrans = ntrans
        self.lock = lock
        self.data = data

    @override
    def __repr__(self) -> str:
        return f"Cycle({self.kind.letter}, address=0x{self.address:08X}, nopc={self.nopc})"


class Recorder:
    __slots__ = ("cycles",)

    cycles: list[Cycle]

    def __init__(self) -> None:
        self.cycles = []

    def add(self, cycle: Cycle) -> Cycle:
        self.cycles.append(cycle)
        return cycle

    def clear(self) -> None:
        self.cycles = []

    def spent(self) -> Cycles:
        counted = {one.letter: 0 for one in TYPES}
        for one in self.cycles:
            counted[one.kind.letter] += 1
        return Cycles(
            s=counted["S"],
            n=counted["N"],
            i=counted["I"],
            c=counted["C"],
        )

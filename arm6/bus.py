"""What ARM60 drives on its pins, one cycle at a time, with the pipelining kept.

Table 3 gives four cycle types and the two pins that name them. `Nmreq` and `seq`
are generated while `mclk` is LOW in the cycle *before* the one whose
characteristics they forecast, which the datasheet says is what gives the memory
system time to decide whether it can use a page mode access. The address, `Nbw`,
`Nrw` and `Nopc` appear up to half a cycle ahead and describe the cycle they are
printed in.

So one record here is one row of a chapter 10 table: the access that row performs
and, separately, the type that row forecasts. Table 20 counts the forecasts, and
that is checked rather than asserted: adding up the forecasts of every row in
every table reproduces Table 20's figures for all eleven forms.
"""

from __future__ import annotations

from typing import override

from arm6.tally import Cycles


class CycleType:
    """One of the four combinations of `Nmreq` and `seq` that Table 3 names."""

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
        """Whether the cycle asks the memory system for anything.

        `Nmreq` LOW is the request. An internal cycle and a coprocessor register
        transfer both leave it HIGH, which is why neither can be aborted and why
        the datasheet says an internal cycle can be merged with the sequential
        access that follows it.
        """
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
    """One row of a chapter 10 table.

    `kind` is the type this row forecasts, which is the one Table 20 counts
    against the instruction. The address and the three half-cycle-ahead pins
    describe the access the row itself performs, which is a different cycle, and
    keeping the two apart is the whole reason this class is not a single integer.
    """

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
    """The cycles one instruction drove, kept so a caller can read the bus.

    A count is not a comparison: a model can spend the right number of cycles
    driving the wrong addresses. Keeping the rows is what lets a check compare
    against the table rather than against the total.
    """

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
        """What the rows add up to, in the four types Table 20 states costs in."""
        counted = {one.letter: 0 for one in TYPES}
        for one in self.cycles:
            counted[one.kind.letter] += 1
        return Cycles(
            s=counted["S"],
            n=counted["N"],
            i=counted["I"],
            c=counted["C"],
        )

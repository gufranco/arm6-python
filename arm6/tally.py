"""The cycle tally, in the four types ARM60 Table 3 defines.

Every other clocked member of this family reports one integer and stops, because
the parts they model settle a memory access in a fixed number of their own
cycles. ARM60 does not. Section 8.6 states that `mclk` may be stretched without
limit and that `Nwait` may insert whole cycles instead, and the pin table adds
that `Nwait` may be tied HIGH in a system that needs none. How long a cycle takes
is therefore a property of the board, so a model that published one number of
ticks would be publishing a board fact nobody measured.

`step` still returns an integer, because the family's interface promises one and
because the datasheet's own summary adds the four types together when it says a
multiply takes at most `1S+16I` cycles. That integer is the cycle count, which is
also the tick count in the one configuration the pin table names outright:
`Nwait` tied HIGH, one `mclk` per cycle. Anything else is a board fact, and
`Cycles.ticks` is where a caller supplies theirs.

The breakdown behind that integer is kept on the part rather than on the integer.
CPython refuses a non-empty `__slots__` on a subclass of `int`, because `int` is
variable length, and the family requires every published class to declare its
slots. The two cannot both be satisfied on one object, so the count and the
breakdown are two objects: `step` returns the count, and `spent` holds the
breakdown of the instruction that produced it.
"""

from __future__ import annotations

from typing import Any, NoReturn, override

from arm6.errors import BadWaits, WaitsRequired

LINES = ("sequential", "nonsequential", "internal", "coprocessor")
"""The four wait figures a board has to state, in the order they are reported.

Named for the cycle types rather than for the pins, because a caller supplying
them is describing their own memory system rather than reading ARM60's bus.
"""

TYPES = ("s", "n", "i", "c")
"""The four cycle types, spelled as ARM60 Table 3 and Table 20 spell them."""


class Frozen:
    """A value that refuses to be written to after it is built.

    Slots alone stop a name the class does not have. They do not stop a write to
    one it does, and a tally that can be edited in place is a tally a caller can
    quietly disagree with the model about. Both classes here are measurements, so
    neither has a legitimate write after construction.
    """

    __slots__ = ()

    @override
    def __setattr__(self, name: str, value: Any) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is a measurement and does not change")

    @override
    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is a measurement and does not change")


class Waits(Frozen):
    """What one cycle of each type costs on a particular board, in `mclk` periods.

    Every figure is required and none has a default. A default here would be an
    invented board, and the one that looks harmless is the worst of them: all
    ones is the `Nwait` tied HIGH configuration, which a caller who had not
    chosen it would be handed silently. Stating all four is cheap, and it is the
    whole reason this class exists rather than a bare integer.
    """

    __slots__ = LINES

    sequential: int
    nonsequential: int
    internal: int
    coprocessor: int

    def __init__(
        self,
        *,
        sequential: int,
        nonsequential: int,
        internal: int,
        coprocessor: int,
    ) -> None:
        given = (sequential, nonsequential, internal, coprocessor)
        for name, value in zip(LINES, given, strict=True):
            if value < 1:
                raise BadWaits(
                    f"{name} is {value}: a cycle costs at least one mclk period, so a "
                    "figure below one describes an access completing in no time"
                )
            object.__setattr__(self, name, value)

    @override
    def __repr__(self) -> str:
        shown = ", ".join(f"{name}={getattr(self, name)}" for name in LINES)
        return f"Waits({shown})"


class Cycles(Frozen):
    """What an instruction cost, kept as four counts rather than collapsed into one.

    S, N, I and C are ARM60's own four cycle types, decided by `Nmreq` and `seq`
    as Table 3 sets out, and Table 20 states every instruction's cost in exactly
    these terms. Keeping them apart is what lets a caller with a real board work
    out a real duration, and what stops this package from pretending to know one.
    """

    __slots__ = TYPES

    s: int
    n: int
    i: int
    c: int

    def __init__(self, s: int = 0, n: int = 0, i: int = 0, c: int = 0) -> None:
        object.__setattr__(self, "s", s)
        object.__setattr__(self, "n", n)
        object.__setattr__(self, "i", i)
        object.__setattr__(self, "c", c)

    @property
    def total(self) -> int:
        """The cycle count, which is the tick count with `Nwait` tied HIGH.

        The datasheet adds the types together itself when it says the longest
        multiply is `1S+16I` cycles, so this is the manufacturer's arithmetic
        rather than a shortcut. It becomes a duration only through `ticks`.
        """
        return self.s + self.n + self.i + self.c

    def __add__(self, other: object) -> Cycles:
        if not isinstance(other, Cycles):
            return NotImplemented
        return Cycles(
            s=self.s + other.s,
            n=self.n + other.n,
            i=self.i + other.i,
            c=self.c + other.c,
        )

    def __radd__(self, other: Any) -> Cycles:
        if other == 0:
            return self
        return NotImplemented

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Cycles):
            return NotImplemented
        return (self.s, self.n, self.i, self.c) == (other.s, other.n, other.i, other.c)

    @override
    def __hash__(self) -> int:
        return hash((self.s, self.n, self.i, self.c))

    @override
    def __repr__(self) -> str:
        shown = ", ".join(f"{name}={getattr(self, name)}" for name in TYPES)
        return f"Cycles({shown})"

    def ticks(self, waits: Waits | None) -> int:
        """How many `mclk` periods this cost on the board the caller describes.

        Refusing a missing argument rather than defaulting is the point of the
        method. The datasheet does not say how long a cycle takes, so neither
        does this package, and a caller who has not measured their memory system
        gets a refusal that says why instead of a number that looks measured.
        """
        if waits is None:
            raise WaitsRequired(
                "ARM60 puts memory timing on the Nwait pin and section 8.6 states the "
                "clock may be stretched without limit, so how long a cycle takes is a "
                "fact about the board. Supply Waits(...) describing yours."
            )
        return (
            self.s * waits.sequential
            + self.n * waits.nonsequential
            + self.i * waits.internal
            + self.c * waits.coprocessor
        )

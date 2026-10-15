from __future__ import annotations

from typing import Any, NoReturn, override

from arm6.errors import BadWaits, WaitsRequired

LINES = ("sequential", "nonsequential", "internal", "coprocessor")

TYPES = ("s", "n", "i", "c")


class Frozen:
    __slots__ = ()

    @override
    def __setattr__(self, name: str, value: Any) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is a measurement and does not change")

    @override
    def __delattr__(self, name: str) -> NoReturn:
        raise AttributeError(f"{type(self).__name__} is a measurement and does not change")


class Waits(Frozen):
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

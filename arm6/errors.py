"""Everything this package raises, defined once.

This module imports nothing from the package, so it can never be the far end of
an import cycle. Every other module reaches its exceptions through here, which
is what stops one name acquiring two definitions: `except UnknownModelError`
written against one module and sailing straight through against another is a
trap that looks like it works.
"""

from __future__ import annotations


class Arm6Error(Exception):
    """The root every failure here descends from.

    A caller that wants to catch anything this package raises catches this one
    name. Nothing raises it directly.
    """

    __slots__ = ()


class UnknownModelError(Arm6Error):
    """A name no model in the catalogue answers to.

    The message lists every model there is, so a caller who did not know what to
    pass learns it from the refusal rather than from the source. Naming no model
    at all raises the same class for the same reason: there is no default here
    and a constructor that invents one cannot report a mistake.
    """

    __slots__ = ()


class Truncated(Arm6Error):
    """An offset with no whole instruction at it.

    Raised by the disassembler rather than by the core, because a core that runs
    off the end of memory has already been given a memory that answers, and a
    reader walking an image has not. The offset is carried so a caller can say
    where the image ran out.
    """

    __slots__ = ("offset",)

    def __init__(self, offset: int) -> None:
        self.offset = offset
        super().__init__(f"no whole instruction at offset {offset}")


class RunLimit(Arm6Error):
    """A bounded run gave up rather than hanging.

    `run_until` takes a limit because a predicate that never becomes true is the
    normal outcome of a mistake, and a model that spins on it reports nothing.
    """

    __slots__ = ()


class ClockClosed(Arm6Error):
    """The clock was driven after it was shut down.

    `Clock` runs the part on a thread so a host can suspend it between any two
    cycles. Once closed the thread is gone, and asking it for another cycle is a
    caller error rather than something to answer with a silent no-op.
    """

    __slots__ = ()


class WaitsRequired(Arm6Error):
    """A tick count was asked for without saying what the board costs.

    ARM60 puts memory timing on the `Nwait` pin and the datasheet states the
    clock may be stretched without limit, so the number of ticks a cycle takes
    is a fact about the board rather than about the part. This package counts
    S, N, I and C cycles and refuses to convert them into ticks until a caller
    supplies the wait states their own memory system imposes.
    """

    __slots__ = ()


class BadWaits(Arm6Error):
    """Wait states no memory system could impose.

    A cycle costs at least one `mclk` period, so a figure below one describes an
    access completing in no time. Refusing it here keeps the refusal next to the
    number rather than letting it surface as an impossible tally later.
    """

    __slots__ = ()

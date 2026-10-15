from __future__ import annotations


class Arm6Error(Exception):
    __slots__ = ()


class UnknownModelError(Arm6Error):
    __slots__ = ()


class Truncated(Arm6Error):
    __slots__ = ("offset",)

    def __init__(self, offset: int) -> None:
        self.offset = offset
        super().__init__(f"no whole instruction at offset {offset}")


class RunLimit(Arm6Error):
    __slots__ = ()


class ClockClosed(Arm6Error):
    __slots__ = ()


class WaitsRequired(Arm6Error):
    __slots__ = ()


class BadWaits(Arm6Error):
    __slots__ = ()

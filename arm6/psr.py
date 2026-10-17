from __future__ import annotations

from typing import override

from arm6.errors import Arm6Error

N_BIT = 31
Z_BIT = 30
C_BIT = 29
V_BIT = 28
I_BIT = 7
F_BIT = 6

MODE_MASK = 0b11111


class UnknownMode(Arm6Error):
    __slots__ = ()


class Mode:
    __slots__ = ("bank", "bits", "name", "privileged", "spsr", "wide")

    name: str
    bits: int
    wide: bool
    privileged: bool
    bank: str
    spsr: str | None

    def __init__(
        self,
        name: str,
        bits: int,
        wide: bool,
        privileged: bool,
        bank: str,
        spsr: str | None,
    ) -> None:
        self.name = name
        self.bits = bits
        self.wide = wide
        self.privileged = privileged
        self.bank = bank
        self.spsr = spsr

    @override
    def __repr__(self) -> str:
        return f"Mode({self.name}, bits=0b{self.bits:05b})"


def _catalogue() -> dict[str, Mode]:
    made = [
        Mode("usr32", 0b10000, True, False, "usr", None),
        Mode("fiq32", 0b10001, True, True, "fiq", "fiq"),
        Mode("irq32", 0b10010, True, True, "irq", "irq"),
        Mode("svc32", 0b10011, True, True, "svc", "svc"),
        Mode("abt32", 0b10111, True, True, "abt", "abt"),
        Mode("und32", 0b11011, True, True, "und", "und"),
        Mode("usr26", 0b00000, False, False, "usr", None),
        Mode("fiq26", 0b00001, False, True, "fiq", "fiq"),
        Mode("irq26", 0b00010, False, True, "irq", "irq"),
        Mode("svc26", 0b00011, False, True, "svc", "svc"),
    ]
    return {one.name: one for one in made}


MODES = _catalogue()

BY_BITS = {one.bits: one for one in MODES.values()}

BANKS = ("usr", "fiq", "irq", "svc", "abt", "und")

SPSR_BANKS = tuple(name for name in BANKS if name != "usr")


def mode_for(bits: int) -> Mode | None:
    return BY_BITS.get(bits & MODE_MASK)


def mode_of(value: int) -> Mode:
    found = mode_for(value)
    if found is None:
        raise UnknownMode(
            f"M[4:0]=0b{value & MODE_MASK:05b} names no ARM60 mode; "
            "section 5.2 and Table 1 give ten, and Application Note 11 gives the four "
            "26-bit encodings among them"
        )
    return found


def with_mode(value: int, mode: Mode) -> int:
    return (value & ~MODE_MASK) | mode.bits


def flag(value: int, bit: int) -> bool:
    return bool(value >> bit & 1)


def with_flag(value: int, bit: int, held: bool) -> int:
    if held:
        return value | 1 << bit
    return value & ~(1 << bit) & 0xFFFFFFFF

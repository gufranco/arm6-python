"""The status register: which bits are defined, and which ten modes exist.

Two things here look like details and decide a great deal.

ARM60 section 7.4.2 states that only eleven bits of the PSR are defined and that
`PSR[27:8,5]` are reserved. Bit 5 is named in that list, in prose, by the
manufacturer. On the ARM7TDMI, which is the part the published conformance
corpus was recorded from, bit 5 is the Thumb bit. That single sentence is what
makes this a different register from the one that corpus describes, and it is
rung one rather than an inference from the architecture's history.

Section 5.2 says ten modes are reachable when the part is configured for a 32-bit
program space, while Table 1 prints six. The four missing encodings are not in
the ARM60 datasheet at all, nor in the ARM610 datasheet, whose Table 2 is
identical. They are in Application Note 11, Table 1, which the datasheet names
and which is pinned beside it. Filling them in from anywhere else would have been
inventing four modes.
"""

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

RESERVED_MASK = 0x0FFFFF20
"""`PSR[27:8,5]`, quoted from section 7.4.2 rather than derived from the figure.

Bits 27 down to 8 give `0x0FFFFF00`, and bit 5 adds `0x20`. Figure 4 draws bit 5
unlabelled between F and M4, which agrees, but the prose is what names it.
"""

DEFINED_MASK = (1 << N_BIT) | (1 << Z_BIT) | (1 << C_BIT) | (1 << V_BIT)
DEFINED_MASK |= (1 << I_BIT) | (1 << F_BIT) | MODE_MASK
"""N, Z, C, V, I, F and M[4:0]: the eleven bits section 7.4.2 says are defined.

Together with the reserved mask this is the whole word and the two do not
overlap, which is checked rather than asserted. A partition that fails would mean
one of the two masks had drifted from the sentence it came from.
"""


class UnknownMode(Arm6Error):
    """A mode field holding an encoding no ARM60 mode uses.

    Section 5.2 and Table 1 between them enumerate ten, and the datasheet adds
    that only the modes explicitly described shall be used. What the silicon does
    with the other twenty-two encodings is not stated anywhere, so this refuses
    rather than picking the nearest one. `mode_for` is the way to ask without
    being refused.
    """

    __slots__ = ()


class Mode:
    """One operating mode: its encoding, its bank, and whether it is privileged.

    `wide` separates the two overlapping sets Application Note 11 describes. A
    wide mode carries the 32-bit program counter in R15 and the status bits in a
    register of their own; a narrow one reverts to the earlier arrangement where
    R15 holds both.
    """

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
    """The ten modes, six from Table 1 and four from Application Note 11.

    Built here rather than written out as a literal so that the two sources stay
    visibly separate: the `wide` column is exactly the split between the table
    the datasheet prints and the table it does not.
    """
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
"""The six register banks the ten modes share between them.

Application Note 11: the two sets of User, FIQ, IRQ and Supervisor modes each
share a set of banked registers, and Abort and Undefined have a pair each.
"""

SPSR_BANKS = tuple(name for name in BANKS if name != "usr")
"""The five saved status registers, one per mode a exception can enter."""


def mode_for(bits: int) -> Mode | None:
    """The mode an encoding names, or nothing when no mode uses it."""
    return BY_BITS.get(bits & MODE_MASK)


def mode_of(value: int) -> Mode:
    """The mode a status register word is in, refusing an encoding no mode uses.

    Refusing matters most for `0b11111`. That is System mode on the ARM7TDMI and
    it is absent from ARM60 Table 1 and from ARM610 Table 2, so a corpus case
    carrying it describes a mode this part does not have. Answering with the
    nearest mode would turn that into a passing comparison.
    """
    found = mode_for(value)
    if found is None:
        raise UnknownMode(
            f"M[4:0]=0b{value & MODE_MASK:05b} names no ARM60 mode; "
            "section 5.2 and Table 1 give ten, and Application Note 11 gives the four "
            "26-bit encodings among them"
        )
    return found


def with_mode(value: int, mode: Mode) -> int:
    """The same status word in a different mode, every other bit untouched.

    Section 7.4.1 asks for a read-modify-write when altering control bits,
    because an eight-bit immediate cannot preserve the reserved ones. Keeping the
    rest of the word is that rule expressed as the only way to change a mode.
    """
    return (value & ~MODE_MASK) | mode.bits


def flag(value: int, bit: int) -> bool:
    return bool(value >> bit & 1)


def with_flag(value: int, bit: int, held: bool) -> int:
    if held:
        return value | 1 << bit
    return value & ~(1 << bit) & 0xFFFFFFFF

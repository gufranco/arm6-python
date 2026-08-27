"""Thirty seven registers, banked the way the programmer's model banks them.

ARM60 page 10: thirty one general purpose registers and six status registers.
Page 1 of the same document says the part has a bank of twenty seven, which is
the earlier part's figure carried into the text when the document was adapted;
the block diagram on page 2 prints thirty one general and six status, and the
ARM610 datasheet agrees. Page 1 is the erratum and it is recorded rather than
quietly followed.

Which registers a mode sees is the whole reason this module exists. R0 to R7 are
common to every mode. R8 to R12 are common except in FIQ, which banks all five.
R13 and R14 are banked in every mode. R15 is the program counter and is never
banked. Application Note 11 adds that the four 26-bit modes share their banks
with the 32-bit modes of the same name, which is why the bank is looked up by the
mode's `bank` rather than by its name.
"""

from __future__ import annotations

import random

from arm6 import psr

WORD_MASK = 0xFFFFFFFF

COMMON = 8
"""R0 to R7, seen by every mode."""

LOW_BANKED = 5
"""R8 to R12, seen by every mode except FIQ, which has its own five."""

GENERAL_COUNT = 31
"""What page 10 states: sixteen visible at once, and fifteen more behind banks.

R0 to R7 and R15 are one copy each, which is nine. R8 to R12 are two copies,
which is ten. R13 and R14 are six copies each, which is twelve. Nine plus ten
plus twelve is thirty one, and the count is derived here rather than written down
so that it cannot disagree with the banking below it.
"""

STATUS_COUNT = 6
"""One CPSR and five SPSRs, one per mode an exception can enter."""


def _derive(seed: int, index: int) -> int:
    """What a register holds when the rail comes up, reproducible from the seed."""
    return random.Random((seed << 24) ^ index).randrange(1 << 32)


class Registers:
    """The register file, including the banks the current mode cannot see.

    Nothing here arrives cleared. Construction puts every register in the state
    the rail coming up leaves it, the program counter included, so a newly built
    part executes rubbish from a rubbish address exactly as the silicon would.
    `fill` is the one way across this family to ask for something else, and it
    exists for runs that have to get through a few dozen instructions rather than
    for convenience.
    """

    __slots__ = ("banked", "common", "cpsr", "fiq_low", "low", "pc", "spsr")

    common: list[int]
    low: list[int]
    fiq_low: list[int]
    banked: dict[str, list[int]]
    pc: int
    cpsr: int
    spsr: dict[str, int]

    def __init__(self, seed: int, fill: int | None = None) -> None:
        def start(index: int) -> int:
            if fill is not None:
                return fill & WORD_MASK
            return _derive(seed, index)

        self.common = [start(one) for one in range(COMMON)]
        self.low = [start(0x100 + one) for one in range(LOW_BANKED)]
        self.fiq_low = [start(0x200 + one) for one in range(LOW_BANKED)]
        self.banked = {
            name: [start(0x300 + place * 2), start(0x300 + place * 2 + 1)]
            for place, name in enumerate(psr.BANKS)
        }
        self.pc = start(0x400)
        self.cpsr = start(0x500) if fill is None else fill & WORD_MASK
        self.cpsr = psr.with_mode(self.cpsr, psr.MODES["svc32"])
        self.spsr = {name: start(0x600 + place) for place, name in enumerate(psr.SPSR_BANKS)}

    def general_count(self) -> int:
        return (
            len(self.common)
            + 1
            + len(self.low)
            + len(self.fiq_low)
            + sum(len(one) for one in self.banked.values())
        )

    def status_count(self) -> int:
        return 1 + len(self.spsr)

    @property
    def mode(self) -> psr.Mode:
        return psr.mode_of(self.cpsr)

    def read(self, index: int) -> int:
        """One register as the current mode sees it.

        R15 answers with its bottom two bits clear, which is what page 10 states:
        when R15 is read, bits [1:0] are zero and bits [31:2] contain the PC.
        What the pipeline adds to that is the instruction's business, not the
        register file's.
        """
        if index < COMMON:
            return self.common[index]
        if index == 15:
            return self.pc & ~0b11 & WORD_MASK
        mode = self.mode
        if index < COMMON + LOW_BANKED:
            held = self.fiq_low if mode.bank == "fiq" else self.low
            return held[index - COMMON]
        return self.banked[mode.bank][index - 13]

    def write(self, index: int, value: int) -> None:
        value &= WORD_MASK
        if index < COMMON:
            self.common[index] = value
            return
        if index == 15:
            self.pc = value
            return
        mode = self.mode
        if index < COMMON + LOW_BANKED:
            held = self.fiq_low if mode.bank == "fiq" else self.low
            held[index - COMMON] = value
            return
        self.banked[mode.bank][index - 13] = value

    def saved(self) -> int | None:
        """The current mode's saved status register, or nothing in a user mode.

        A user mode has no SPSR, and answering with one would invent a register
        the programmer's model does not give it.
        """
        bank = self.mode.spsr
        if bank is None:
            return None
        return self.spsr[bank]

    def save(self, value: int) -> None:
        """Put a word in the current mode's saved status register, if it has one.

        In a user mode this does nothing, which is what the silicon does: there
        is no register to write to and no fault is raised.
        """
        bank = self.mode.spsr
        if bank is None:
            return
        self.spsr[bank] = value & WORD_MASK

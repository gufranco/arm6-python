from __future__ import annotations

import random

from arm6 import psr

WORD_MASK = 0xFFFFFFFF

COMMON = 8

LOW_BANKED = 5

GENERAL_COUNT = 31

STATUS_COUNT = 6


def _derive(seed: int, index: int) -> int:
    return random.Random((seed << 24) ^ index).randrange(1 << 32)


class Registers:
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
        bank = self.mode.spsr
        if bank is None:
            return None
        return self.spsr[bank]

    def save(self, value: int) -> None:
        bank = self.mode.spsr
        if bank is None:
            return
        self.spsr[bank] = value & WORD_MASK

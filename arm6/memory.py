from __future__ import annotations

import random
from collections.abc import Sequence

UNSET_SEED = 0x5A5A5A5A

ADDRESS_MASK = 0xFFFFFFFF

WORD_MASK = 0xFFFFFFFF

BYTE_MASK = 0xFF


def _derive(seed: int, address: int) -> int:
    return random.Random((seed << 20) ^ address).randrange(0x100)


class Memory:
    __slots__ = ("bigend", "fill", "seed", "written")

    seed: int
    fill: int | None
    bigend: bool
    written: dict[int, int]

    def __init__(
        self,
        image: Sequence[int] | None = None,
        seed: int = UNSET_SEED,
        fill: int | None = None,
        bigend: bool = False,
    ) -> None:
        self.seed = seed
        self.fill = None if fill is None else fill & BYTE_MASK
        self.bigend = bigend
        self.written = {}
        if image is not None:
            for offset, one in enumerate(image):
                self.written[offset] = one & BYTE_MASK

    def read_byte(self, address: int) -> int:
        address &= ADDRESS_MASK
        held = self.written.get(address)
        if held is not None:
            return held
        if self.fill is not None:
            return self.fill
        return _derive(self.seed, address)

    def write_byte(self, address: int, value: int) -> None:
        self.written[address & ADDRESS_MASK] = value & BYTE_MASK

    def read_word(self, address: int) -> int:
        base = address & ADDRESS_MASK & ~0b11
        held = [self.read_byte(base + one) for one in range(4)]
        if self.bigend:
            held.reverse()
        return held[0] | held[1] << 8 | held[2] << 16 | held[3] << 24

    def write_word(self, address: int, value: int) -> None:
        base = address & ADDRESS_MASK & ~0b11
        value &= WORD_MASK
        held = [value >> shift & BYTE_MASK for shift in (0, 8, 16, 24)]
        if self.bigend:
            held.reverse()
        for offset, one in enumerate(held):
            self.write_byte(base + offset, one)

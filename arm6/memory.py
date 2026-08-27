"""The store ARM60 drives, four gigabytes of it, none of it clean.

`a[31:0]` is thirty-two address lines, so the space is four gigabytes and nothing
can allocate it. It is held sparsely: what a caller wrote is remembered, and
everything else is derived from the seed at the moment it is read. That is not an
optimisation. A read of a word nothing wrote is a defect on the board, and a
store that answers zero to it turns that defect into a passing test.

Endianness is a pin. Section 6 gives `bigend` as an input, HIGH for big endian
and LOW for little, and adds that the earlier parts which have no such pin are
little endian. So the order is a fact about the board rather than about the part,
and both are modelled. The default here is little endian because that is the
order the parts without the pin have, and because it has to be something for a
store to be constructible at all; a board that ties the pin the other way says so.
"""

from __future__ import annotations

import random
from collections.abc import Sequence

UNSET_SEED = 0x5A5A5A5A
"""The seed a part gets when nobody chose one.

The same value across the family, so a check written against one member's
scrambled store reads the same on another's.
"""

ADDRESS_MASK = 0xFFFFFFFF

WORD_MASK = 0xFFFFFFFF

BYTE_MASK = 0xFF


def _derive(seed: int, address: int) -> int:
    """The byte at an address nobody wrote, reproducible from the seed.

    Derived at the moment of the read rather than filled in at construction,
    because filling four gigabytes is not possible and because a byte that has
    never been read has never needed to exist.
    """
    return random.Random((seed << 20) ^ address).randrange(0x100)


class Memory:
    """Unclean everywhere without being allocated anywhere.

    `fill` is how a caller asks for one byte everywhere, and it is deliberately
    something they have to write. What it is for is a run that has to get through
    a few dozen instructions without meeting an encoding that traps, which is
    what every check of a cycle budget needs and what a scrambled store cannot
    give. It is the one spelling for that request across this family.

    `image` is what a board genuinely knows at power on: the bytes a mask ROM
    holds, laid at the bottom, where ARM60 fetches its reset vector from.
    """

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
        """One byte, whichever way round the board puts them.

        A byte access names a byte, so no reordering happens here. Which byte of
        a word that is depends on the pin, and that is the word helpers' business.
        """
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
        """One word, from the aligned address.

        ARM60 ignores `a[1:0]` for the access itself and rotates the result
        afterwards when the address was unaligned. The rotation belongs to the
        instruction rather than to the store, so it happens in the core and this
        answers what the memory system would have put on `d[31:0]`.
        """
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

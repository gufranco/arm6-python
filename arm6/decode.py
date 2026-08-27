"""Which of Figure 28's eleven rows a word is, and what it is when it is none of them.

Figure 28 prints the whole instruction set on one page. What it does not print
decides as much as what it does: there is no halfword transfer row, no signed
load row, no long multiply row and no branch-and-exchange row, so four of the
files in the published conformance corpus describe encodings this part does not
have. Those are excluded at rung one, from the part's own sheet, rather than by
an inference from the architecture's history.

The rows overlap in their top bits, so the order they are tried in is part of the
decoding. Multiply and swap both read as data processing until the bottom byte is
looked at, and the row the figure marks Undefined is a subset of the single data
transfer row.

There is a twelfth outcome and it is deliberately not a row. The note beneath the
figure says that some codes are not defined and do **not** cause the undefined
instruction trap, giving a multiply with bit 5 or bit 6 set as the example. Those
are a different thing from the Undefined row, which traps, and collapsing the two
would lose the distinction the note exists to draw.
"""

from __future__ import annotations

CONDITIONS = (
    "EQ",
    "NE",
    "CS",
    "CC",
    "MI",
    "PL",
    "VS",
    "VC",
    "HI",
    "LS",
    "GE",
    "LT",
    "GT",
    "LE",
    "AL",
    "NV",
)
"""Figure 5, in the order it numbers them.

`NV` is here because the encoding is, and the datasheet says it shall not be used
because it will be redefined. Leaving it out would make an encoding that exists
unreadable.
"""

DATA_PROCESSING = "data processing"
MULTIPLY = "multiply"
SINGLE_DATA_SWAP = "single data swap"
SINGLE_DATA_TRANSFER = "single data transfer"
UNDEFINED = "undefined"
BLOCK_DATA_TRANSFER = "block data transfer"
BRANCH = "branch"
COPROCESSOR_DATA_TRANSFER = "coprocessor data transfer"
COPROCESSOR_DATA_OPERATION = "coprocessor data operation"
COPROCESSOR_REGISTER_TRANSFER = "coprocessor register transfer"
SOFTWARE_INTERRUPT = "software interrupt"

KINDS = (
    DATA_PROCESSING,
    MULTIPLY,
    SINGLE_DATA_SWAP,
    SINGLE_DATA_TRANSFER,
    UNDEFINED,
    BLOCK_DATA_TRANSFER,
    BRANCH,
    COPROCESSOR_DATA_TRANSFER,
    COPROCESSOR_DATA_OPERATION,
    COPROCESSOR_REGISTER_TRANSFER,
    SOFTWARE_INTERRUPT,
)
"""The eleven rows, in the order Figure 28 prints them."""

UNSPECIFIED = "unspecified"
"""Not a row, and kept out of `KINDS` on purpose.

An encoding that matches none of the eleven and that the note says does not trap.
The datasheet declines to say what the silicon does with it, and Application Note
11 says the behaviour is the ARM2aS macrocell's, a part whose data book is not
pinned here. So this package refuses these rather than choosing an answer.
"""


def condition_of(word: int) -> str:
    """The condition field, which every encoding in Figure 28 carries."""
    return CONDITIONS[word >> 28 & 0xF]


def _is_multiply(word: int) -> bool:
    return word & 0x0FC000F0 == 0x00000090


def _is_swap(word: int) -> bool:
    return word & 0x0FB00FF0 == 0x01000090


def _looks_like_a_multiply(word: int) -> bool:
    """The shape the note beneath Figure 28 warns about.

    A data processing word with a **register-controlled** shift must carry a zero
    in bit 7. A one there means the encoding is a multiply or an undefined
    instruction, so such a word with both bit 7 and bit 4 set is one of the two,
    and if it is not a multiply or a swap then the datasheet has stopped
    describing it.

    Bit 25 is in the mask and it is the whole point. A register-controlled shift
    is only possible when operand 2 is a register, so with bit 25 set the low
    twelve bits are a rotate and an immediate value and bits 7 and 4 are just two
    of that value's bits. Reading the rule without bit 25 turns roughly an eighth
    of every immediate-operand encoding into a refusal.
    """
    return word & 0x0E000090 == 0x00000090


def classify(word: int) -> str:
    """Which row of Figure 28 a word is, or that it is outside the figure.

    Tried in an order the overlaps force. Multiply and swap are looked for before
    data processing because all three live under `00` in bits 27 and 26. The
    Undefined row is looked for before single data transfer because `011` with
    bit 4 set is a subset of `01`.
    """
    if _is_multiply(word):
        return MULTIPLY
    if _is_swap(word):
        return SINGLE_DATA_SWAP
    if _looks_like_a_multiply(word):
        return UNSPECIFIED
    if word & 0x0C000000 == 0x00000000:
        return DATA_PROCESSING
    if word & 0x0E000010 == 0x06000010:
        return UNDEFINED
    if word & 0x0C000000 == 0x04000000:
        return SINGLE_DATA_TRANSFER
    if word & 0x0E000000 == 0x08000000:
        return BLOCK_DATA_TRANSFER
    if word & 0x0E000000 == 0x0A000000:
        return BRANCH
    if word & 0x0E000000 == 0x0C000000:
        return COPROCESSOR_DATA_TRANSFER
    if word & 0x0F000000 == 0x0F000000:
        return SOFTWARE_INTERRUPT
    if word & 0x00000010:
        return COPROCESSOR_REGISTER_TRANSFER
    return COPROCESSOR_DATA_OPERATION

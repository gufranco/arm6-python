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

UNSPECIFIED = "unspecified"


def condition_of(word: int) -> str:
    return CONDITIONS[word >> 28 & 0xF]


def _is_multiply(word: int) -> bool:
    return word & 0x0FC000F0 == 0x00000090


def _is_swap(word: int) -> bool:
    return word & 0x0FB00FF0 == 0x01000090


def _looks_like_a_multiply(word: int) -> bool:
    return word & 0x0E000090 == 0x00000090


def classify(word: int) -> str:
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

"""A word read rather than run, as the instruction it is.

`decode.classify` answers which of Figure 28's eleven rows a word belongs to, and
that is a real question with a real answer. It is not enough to walk an image
with. A caller who wants to know where a routine ends, which address a branch
goes to, or which literal a PC-relative load reaches has to decode the word
again, outside the package, and then there are two decoders that can disagree.

So this is the same shape every other member of this family publishes: an
`Instruction` that knows where it was found, what it is, and how a reader would
write it, plus a `disassemble` that walks. The fields are the family's, with the
two that have no ARM equivalent replaced by the ones that do: a whole word in
place of an opcode byte, and the row of Figure 28 in place of an addressing mode.

Two conventions are this package's own and are named rather than assumed.
Registers 13, 14 and 15 render as `SP`, `LR` and `PC`, because that is how ARM
assembly is written and the datasheet's own R13, R14 and R15 are still available
in every structured field. And `returns` is a convention rather than an encoding,
because this part has no return instruction; see its docstring.
"""

from __future__ import annotations

from collections import namedtuple
from collections.abc import Sequence

from arm6 import decode as rows
from arm6.errors import Truncated

SIZE = 4
"""Every instruction this part has is one word. There is no Thumb here."""

Instruction = namedtuple(
    "Instruction", "address offset word condition mnemonic kind operand size text"
)
"""One decoded instruction and where it was found.

`condition` is the datasheet's own spelling from `decode.CONDITIONS`, and `kind`
is the row from `decode.KINDS`, so both structured fields speak the vocabulary
the rest of the package already uses. `text` speaks assembly instead, which is
lowercase and folds the condition into the mnemonic.

`operand` is the one number the operand field denotes, resolved to an address
wherever the instruction's addressing is self-contained and therefore leaves no
room for doubt: a branch gives its target, a PC-relative load gives the address
the literal sits at. Everywhere else it is the immediate itself, and it is `None`
when the instruction carries no immediate at all.
"""

REGISTERS = (*(f"R{i}" for i in range(13)), "SP", "LR", "PC")

PROGRAM_COUNTER = 15
LINK_REGISTER = 14

DATA_OPERATIONS = (
    "and",
    "eor",
    "sub",
    "rsb",
    "add",
    "adc",
    "sbc",
    "rsc",
    "tst",
    "teq",
    "cmp",
    "cmn",
    "orr",
    "mov",
    "bic",
    "mvn",
)
"""Figure 9, in the order it numbers them."""

NO_DESTINATION = ("tst", "teq", "cmp", "cmn")
"""The four that write no register, which is what makes their encoding free to
carry the status register transfers instead when the S bit is clear.
"""

ONE_SOURCE = ("mov", "mvn")

SHIFTS = ("lsl", "lsr", "asr", "ror")

BLOCK_MODES = {(0, 0): "da", (0, 1): "ia", (1, 0): "db", (1, 1): "ib"}
"""Pre or post, then up or down, which is how the datasheet draws the four."""

UNDEFINED = "undefined"
UNSPECIFIED = "unspecified"


def _register(number: int) -> str:
    return REGISTERS[number]


def _rotated(word: int) -> int:
    """The eight-bit immediate rotated right by twice the four-bit field."""
    value = word & 0xFF
    amount = ((word >> 8) & 0xF) * 2
    return ((value >> amount) | (value << (32 - amount))) & 0xFFFFFFFF


def _shifted(word: int) -> str:
    """Operand two when it is a register, with the shift the datasheet allows.

    A rotate right by zero is not a rotate by zero. The datasheet gives that
    encoding to rotate-right-extended, which shifts in the carry, so it is
    written under its own name rather than left out.
    """
    name = _register(word & 0xF)
    kind = SHIFTS[(word >> 5) & 3]
    if word & (1 << 4):
        return f"{name}, {kind} {_register((word >> 8) & 0xF)}"
    amount = (word >> 7) & 0x1F
    if amount:
        return f"{name}, {kind} #{amount}"
    if kind == "ror":
        return f"{name}, rrx"
    if kind == "lsl":
        return name
    return f"{name}, {kind} #32"


def _operand_two(word: int) -> str:
    if word & (1 << 25):
        return f"#0x{_rotated(word):X}"
    return _shifted(word)


def _branch(word: int, address: int) -> tuple[str, str, int, str]:
    offset = word & 0xFFFFFF
    if offset & 0x800000:
        offset -= 0x1000000
    target = (address + 2 * SIZE + (offset << 2)) & 0xFFFFFFFF
    return ("bl" if word & (1 << 24) else "b"), "", target, f"0x{target:06X}"


def _status_transfer(word: int) -> tuple[str, str, int | None, str]:
    """The two encodings hiding under a comparison that sets no flags.

    Bit 21 separates them: clear reads the register into a general one, set
    writes it. A write reaches the whole register only when bit 16 is set;
    without it the datasheet says only the flag bits move, which it spells with
    the `_flg` suffix.
    """
    which = "spsr" if word & (1 << 22) else "cpsr"
    if not word & (1 << 21):
        return "mrs", "", None, f"{_register((word >> 12) & 0xF)}, {which}"
    if word & (1 << 16):
        return "msr", "", None, f"{which}, {_register(word & 0xF)}"
    operand = _rotated(word) if word & (1 << 25) else None
    return "msr", "", operand, f"{which}_flg, {_operand_two(word)}"


def _data_processing(word: int) -> tuple[str, str, int | None, str]:
    mnemonic = DATA_OPERATIONS[(word >> 21) & 0xF]
    setting = bool(word & (1 << 20))
    if mnemonic in NO_DESTINATION and not setting:
        return _status_transfer(word)
    operand = _rotated(word) if word & (1 << 25) else None
    destination = _register((word >> 12) & 0xF)
    first = _register((word >> 16) & 0xF)
    second = _operand_two(word)
    if mnemonic in ONE_SOURCE:
        body = f"{destination}, {second}"
    elif mnemonic in NO_DESTINATION:
        body = f"{first}, {second}"
    else:
        body = f"{destination}, {first}, {second}"
    return mnemonic, ("s" if setting and mnemonic not in NO_DESTINATION else ""), operand, body


def _multiply(word: int) -> tuple[str, str, None, str]:
    destination = _register((word >> 16) & 0xF)
    first = _register(word & 0xF)
    second = _register((word >> 8) & 0xF)
    setting = "s" if word & (1 << 20) else ""
    if word & (1 << 21):
        third = _register((word >> 12) & 0xF)
        return "mla", setting, None, f"{destination}, {first}, {second}, {third}"
    return "mul", setting, None, f"{destination}, {first}, {second}"


def _swap(word: int) -> tuple[str, str, None, str]:
    suffix = "b" if word & (1 << 22) else ""
    destination = _register((word >> 12) & 0xF)
    source = _register(word & 0xF)
    base = _register((word >> 16) & 0xF)
    return "swp", suffix, None, f"{destination}, {source}, [{base}]"


def _single_data_transfer(word: int, address: int) -> tuple[str, str, int | None, str]:
    """One register to or from memory, with the offset written where it applies.

    Pre-indexed keeps the offset inside the brackets and post-indexed puts it
    after them, which is not decoration: it is the difference between the address
    used and the address left behind. A write-back bit with post-indexing means
    something else again, so it becomes the `t` suffix rather than an exclamation
    mark that would read as write-back twice.
    """
    load = bool(word & (1 << 20))
    pre = bool(word & (1 << 24))
    up = bool(word & (1 << 23))
    write = bool(word & (1 << 21))
    base = (word >> 16) & 0xF
    base_name = "ldr" if load else "str"
    suffix = "b" if word & (1 << 22) else ""
    if not pre and write:
        suffix += "t"
    destination = _register((word >> 12) & 0xF)

    operand: int | None = None
    if word & (1 << 25):
        offset = _shifted(word)
        shown = offset if up else f"-{offset}"
    else:
        immediate = word & 0xFFF
        operand = immediate if up else -immediate
        if base == PROGRAM_COUNTER and pre:
            operand = (address + 2 * SIZE + (immediate if up else -immediate)) & 0xFFFFFFFF
        shown = f"#{'' if up else '-'}0x{immediate:X}"
        if pre and not immediate:
            return base_name, suffix, operand, f"{destination}, [{_register(base)}]"

    if pre:
        inside = f"{destination}, [{_register(base)}, {shown}]{'!' if write else ''}"
        return base_name, suffix, operand, inside
    return base_name, suffix, operand, f"{destination}, [{_register(base)}], {shown}"


def _block_data_transfer(word: int) -> tuple[str, str, None, str]:
    load = "ldm" if word & (1 << 20) else "stm"
    mode = BLOCK_MODES[(bool(word & (1 << 24)), bool(word & (1 << 23)))]
    base = _register((word >> 16) & 0xF)
    write = "!" if word & (1 << 21) else ""
    user = "^" if word & (1 << 22) else ""
    names = ", ".join(_register(i) for i in range(16) if word & (1 << i))
    return load, mode, None, f"{base}{write}, {{{names}}}{user}"


def _software_interrupt(word: int) -> tuple[str, str, int, str]:
    comment = word & 0xFFFFFF
    return "swi", "", comment, f"0x{comment:06X}"


def _coprocessor_data_transfer(word: int) -> tuple[str, str, int, str]:
    load = "ldc" if word & (1 << 20) else "stc"
    long = "l" if word & (1 << 22) else ""
    immediate = (word & 0xFF) << 2
    up = bool(word & (1 << 23))
    operand = immediate if up else -immediate
    base = _register((word >> 16) & 0xF)
    number = (word >> 12) & 0xF
    unit = (word >> 8) & 0xF
    shown = f"#{'' if up else '-'}0x{immediate:X}"
    write = "!" if word & (1 << 21) else ""
    if word & (1 << 24):
        return load, long, operand, f"p{unit}, c{number}, [{base}, {shown}]{write}"
    return load, long, operand, f"p{unit}, c{number}, [{base}], {shown}"


def _coprocessor_data_operation(word: int) -> tuple[str, str, None, str]:
    unit = (word >> 8) & 0xF
    operation = (word >> 20) & 0xF
    destination = (word >> 12) & 0xF
    first = (word >> 16) & 0xF
    second = word & 0xF
    kind = (word >> 5) & 7
    return "cdp", "", None, f"p{unit}, {operation}, c{destination}, c{first}, c{second}, {kind}"


def _coprocessor_register_transfer(word: int) -> tuple[str, str, None, str]:
    mnemonic = "mrc" if word & (1 << 20) else "mcr"
    unit = (word >> 8) & 0xF
    operation = (word >> 21) & 7
    destination = _register((word >> 12) & 0xF)
    first = (word >> 16) & 0xF
    second = word & 0xF
    kind = (word >> 5) & 7
    return mnemonic, "", None, f"p{unit}, {operation}, {destination}, c{first}, c{second}, {kind}"


def _render(word: int, address: int) -> tuple[str, str, str, int | None, str]:
    """The row, the operation, the suffix that belongs to the addressing, and the rest.

    The suffix comes back apart from the operation because assembly does not put
    the condition at the end. It goes between the two, so a conditional
    flag-setting AND is `andnes` and a conditional multiple load is `ldmneia`.
    Joining them here and cutting them apart again later is how that gets wrong.
    """
    base: str
    suffix: str
    operand: int | None
    body: str
    kind = rows.classify(word)
    if kind == rows.BRANCH:
        base, suffix, operand, body = _branch(word, address)
    elif kind == rows.DATA_PROCESSING:
        base, suffix, operand, body = _data_processing(word)
    elif kind == rows.MULTIPLY:
        base, suffix, operand, body = _multiply(word)
    elif kind == rows.SINGLE_DATA_SWAP:
        base, suffix, operand, body = _swap(word)
    elif kind == rows.SINGLE_DATA_TRANSFER:
        base, suffix, operand, body = _single_data_transfer(word, address)
    elif kind == rows.BLOCK_DATA_TRANSFER:
        base, suffix, operand, body = _block_data_transfer(word)
    elif kind == rows.SOFTWARE_INTERRUPT:
        base, suffix, operand, body = _software_interrupt(word)
    elif kind == rows.COPROCESSOR_DATA_TRANSFER:
        base, suffix, operand, body = _coprocessor_data_transfer(word)
    elif kind == rows.COPROCESSOR_DATA_OPERATION:
        base, suffix, operand, body = _coprocessor_data_operation(word)
    elif kind == rows.COPROCESSOR_REGISTER_TRANSFER:
        base, suffix, operand, body = _coprocessor_register_transfer(word)
    elif kind == rows.UNDEFINED:
        base, suffix, operand, body = UNDEFINED, "", None, f"0x{word:08X}"
    else:
        base, suffix, operand, body = UNSPECIFIED, "", None, f"0x{word:08X}"
    return kind, base, suffix, operand, body


def decode(data: Sequence[int], offset: int = 0, address: int = 0) -> Instruction:
    """One word, or `Truncated` when there is not a whole one there."""
    if not 0 <= offset <= len(data) - SIZE:
        raise Truncated(offset)
    word = int.from_bytes(bytes(data[offset : offset + SIZE]), "little")
    kind, base, suffix, operand, body = _render(word, address)
    condition = rows.condition_of(word)
    written = "" if condition == "AL" else condition.lower()
    text = f"{base}{written}{suffix}"
    return Instruction(
        address=address,
        offset=offset,
        word=word,
        condition=condition,
        mnemonic=base + suffix,
        kind=kind,
        operand=operand,
        size=SIZE,
        text=f"{text} {body}" if body else text,
    )


def returns(instruction: Instruction) -> bool:
    """Whether this is where a routine hands control back.

    A convention, not an encoding. This part has no return instruction: it has a
    program counter that any instruction may write, so what a return looks like
    is whatever the compiler emitted. The two shapes recognised here are the two
    that appear in practice, moving the link register into the counter and
    popping the counter off the stack, and a walk that stops on them stops where
    a reader would say the routine ends.

    Anything else that writes the counter, a computed jump into a table most of
    all, is not recognised and is not meant to be. Guessing there would end a
    walk in the middle of a routine and call it the end.
    """
    if instruction.kind == rows.BLOCK_DATA_TRANSFER:
        loading = bool(instruction.word & (1 << 20))
        return loading and bool(instruction.word & (1 << PROGRAM_COUNTER))
    if instruction.kind != rows.DATA_PROCESSING or instruction.mnemonic != "mov":
        return False
    destination = (instruction.word >> 12) & 0xF
    immediate = bool(instruction.word & (1 << 25))
    return (
        destination == PROGRAM_COUNTER
        and not immediate
        and (instruction.word & 0xFFF) == LINK_REGISTER
    )


def disassemble(
    data: Sequence[int],
    offset: int = 0,
    address: int = 0,
    count: int | None = None,
    stop_at_return: bool = False,
) -> list[Instruction]:
    """Straight through the image from where it is told to start.

    Straight through, and that is the whole of it: this follows no branch and
    takes no jump. A caller wanting reachable code walks it themselves, which is
    the only way to do it correctly, because whether a word is code at all
    depends on how control got there.
    """
    listing: list[Instruction] = []
    while count is None or len(listing) < count:
        try:
            instruction = decode(data, offset, address)
        except Truncated:
            break
        listing.append(instruction)
        offset += instruction.size
        address = (address + instruction.size) & 0xFFFFFFFF
        if stop_at_return and returns(instruction):
            break
    return listing

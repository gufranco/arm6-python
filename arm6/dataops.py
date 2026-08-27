"""The data processing row, the multiply row, and the PSR transfers hidden inside one.

Three things here come straight off the page and are worth naming.

The multiplier is a 2 bit Booth's algorithm with early termination, so it eats
two bits of Rs per cycle and `m` runs to sixteen. The part the published corpus
was recorded from eats eight bits per cycle and its `m` runs to four. Both
terminate early; the radix is the difference, and it is the reason the corpus's
transaction stream is a different part's bus.

`MUL` with Rd equal to Rm gives a zero result and `MLA` gives a meaningless one.
That is a stated behaviour rather than an unpredictable, which is why corpus
cases carrying it are filtered out: ARM60 answers, and the generator's part only
prohibits.

The C flag after a multiply is set to a meaningless value, in the datasheet's own
words. So it is derived from the seed rather than left as whatever happened to be
there, because a value that looks stable is a value somebody will rely on.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, override

from arm6 import psr
from arm6.bus import INTERNAL, NONSEQUENTIAL, SEQUENTIAL
from arm6.shifter import by_amount, by_register

if TYPE_CHECKING:  # pragma: no cover
    from arm6.core import Cpu

WORD_MASK = 0xFFFFFFFF

SIGN = 0x80000000

LOGICAL = frozenset({0b0000, 0b0001, 0b1000, 0b1001, 0b1100, 0b1101, 0b1110, 0b1111})
"""AND, EOR, TST, TEQ, ORR, MOV, BIC and MVN, quoted from section 7.3.1.

The classification decides the flags: a logical operation leaves V alone and
takes C from the barrel shifter, an arithmetic one sets V on an overflow into bit
31 and takes C from the carry out of bit 31 of the ALU.
"""

NO_RESULT = frozenset({0b1000, 0b1001, 0b1010, 0b1011})
"""TST, TEQ, CMP and CMN, which set flags and write nothing."""

MAX_BOOTH = 16


class Outcome:
    """What the ALU produced and which flags it is entitled to touch."""

    __slots__ = ("c", "n", "result", "touches_v", "v", "writes", "z")

    result: int
    n: bool
    z: bool
    c: bool
    v: bool
    touches_v: bool
    writes: bool

    def __init__(
        self,
        result: int,
        n: bool,
        z: bool,
        c: bool,
        v: bool,
        touches_v: bool,
        writes: bool,
    ) -> None:
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "n", n)
        object.__setattr__(self, "z", z)
        object.__setattr__(self, "c", c)
        object.__setattr__(self, "v", v)
        object.__setattr__(self, "touches_v", touches_v)
        object.__setattr__(self, "writes", writes)

    @override
    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("an ALU outcome is a measurement and does not change")


def booth_cycles(multiplier: int) -> int:
    """`m`, from the rule Table 20 states rather than from a loop.

    Multiplication by any number between `2^(2m-3)` and `2^(2m-1)-1` takes
    `1S+mI` for `1<m<16`; by 0 or 1 it takes `1S+1I`; and by anything at or above
    `2^29` it takes `1S+16I`. Those bands are two bits wide, which is the 2 bit
    Booth radix showing through, so the band a value falls in follows from its
    width alone.
    """
    return min(MAX_BOOTH, ((multiplier & WORD_MASK).bit_length() + 2) // 2)


def _add(first: int, second: int, carry_in: bool) -> Outcome:
    """One 33 bit addition, which is every arithmetic operation on this part.

    Subtraction is the same adder with the second operand inverted and a carry
    in, which is why C after a subtraction is a carry rather than a borrow: the
    datasheet says the C flag is set to the carry out of bit 31 of the ALU, and
    that is what this produces without a second rule.
    """
    total = first + second + int(carry_in)
    result = total & WORD_MASK
    carry = total > WORD_MASK
    overflow = bool((first ^ result) & (second ^ result) & SIGN)
    return Outcome(
        result=result,
        n=bool(result & SIGN),
        z=result == 0,
        c=carry,
        v=overflow,
        touches_v=True,
        writes=True,
    )


def _logical(result: int, carry: bool) -> Outcome:
    result &= WORD_MASK
    return Outcome(
        result=result,
        n=bool(result & SIGN),
        z=result == 0,
        c=carry,
        v=False,
        touches_v=False,
        writes=True,
    )


def alu(opcode: int, first: int, second: int, carry: bool) -> Outcome:
    """One of the sixteen operations Table 2 lists, with the flags section 7.3.1 gives."""
    first &= WORD_MASK
    second &= WORD_MASK
    if opcode in {0b0000, 0b1000}:
        held = _logical(first & second, carry)
    elif opcode in {0b0001, 0b1001}:
        held = _logical(first ^ second, carry)
    elif opcode in {0b0010, 0b1010}:
        held = _add(first, ~second & WORD_MASK, True)
    elif opcode == 0b0011:
        held = _add(second, ~first & WORD_MASK, True)
    elif opcode in {0b0100, 0b1011}:
        held = _add(first, second, False)
    elif opcode == 0b0101:
        held = _add(first, second, carry)
    elif opcode == 0b0110:
        held = _add(first, ~second & WORD_MASK, carry)
    elif opcode == 0b0111:
        held = _add(second, ~first & WORD_MASK, carry)
    elif opcode == 0b1100:
        held = _logical(first | second, carry)
    elif opcode == 0b1101:
        held = _logical(second, carry)
    elif opcode == 0b1110:
        held = _logical(first & ~second, carry)
    else:
        held = _logical(~second, carry)
    if opcode in NO_RESULT:
        return Outcome(
            result=held.result,
            n=held.n,
            z=held.z,
            c=held.c,
            v=held.v,
            touches_v=held.touches_v,
            writes=False,
        )
    return held


def immediate(word: int, carry: bool) -> tuple[int, bool]:
    """The eight bit immediate, rotated right by twice the rotate field.

    Section 7.3.3 gives the value and the rotate and stops there: it does not say
    what the shifter's carry output is. The rule modelled here, that a rotate of
    zero passes the old flag through and any other rotate takes bit 31 of the
    result, is the corpus's rather than the document's, and it is recorded as
    such in divergences.json.
    """
    rotate = (word >> 8 & 0xF) * 2
    value = word & 0xFF
    if rotate == 0:
        return value, carry
    value = (value >> rotate | value << (32 - rotate)) & WORD_MASK
    return value, bool(value & SIGN)


def _meaningless_carry(cpu: Cpu, first: int, second: int) -> bool:
    """The C flag after a multiply, which section 7.5.2 calls meaningless.

    Reproducible from the seed and the operands so that a run repeats, and
    deliberately not stable across operands so that nobody can come to rely on it.
    """
    return bool(random.Random((cpu.seed << 8) ^ first ^ (second << 1)).getrandbits(1))


def _operand_two(cpu: Cpu, word: int) -> tuple[int, bool, bool]:
    """Operand 2, the shifter carry it produced, and whether a register shifted it."""
    carry = psr.flag(cpu.registers.cpsr, psr.C_BIT)
    if word & 1 << 25:
        value, out = immediate(word, carry)
        return value, out, False
    kind = word >> 5 & 0b11
    source = word & 0xF
    if word & 1 << 4:
        amount = cpu.read_register(word >> 8 & 0xF) & 0xFF
        value, out = by_register(
            kind, cpu.read_register(source, register_shift=True), amount, carry
        )
        return value, out, True
    value, out = by_amount(kind, cpu.read_register(source), word >> 7 & 0x1F, carry)
    return value, out, False


def _psr_transfer(cpu: Cpu, word: int) -> bool:
    """MRS and MSR, which live inside the data processing row.

    Application Note 11: they are formed from the TST, TEQ, CMP and CMN opcodes
    with the S flag clear, which were previously unused. Figure 14 gives the three
    encodings and they are matched here exactly rather than by opcode alone,
    because an encoding in that space which matches none of them is a reserved
    one rather than a transfer.
    """
    if word & 0x0FBF0FFF == 0x010F0000:
        source = cpu.registers.saved() if word & 1 << 22 else cpu.registers.cpsr
        cpu.registers.write(word >> 12 & 0xF, cpu.registers.cpsr if source is None else source)
        return True
    if word & 0x0FBFFFF0 == 0x0129F000:
        _write_psr(cpu, word, cpu.registers.read(word & 0xF), whole=True)
        return True
    if word & 0x0DBFF000 == 0x0128F000:
        value, _ = (
            immediate(word, False) if word & 1 << 25 else (cpu.registers.read(word & 0xF), False)
        )
        _write_psr(cpu, word, value, whole=False)
        return True
    return False


FLAGS_MASK = 0xF0000000
"""N, Z, C and V: the four bits the flags-only form of MSR writes.

Section 7.4.3: the most significant four bits of the register contents are
written to the N, Z, C and V flags respectively.
"""


def _write_psr(cpu: Cpu, word: int, value: int, whole: bool) -> None:
    """Put a word into the CPSR or the current mode's SPSR.

    Section 7.4.1: in User mode the control bits of the CPSR are protected from
    change, so only the condition code flags move. In a privileged mode the whole
    form writes the whole word.

    The reserved bits are written along with everything else, which is worth
    saying because the opposite is the tempting reading. Section 7.4.2 does say
    the reserved bits shall be preserved, but it says it under a heading that
    introduces rules a *program* should observe to stay compatible with future
    processors. It is advice to whoever writes the MSR, not a statement that the
    silicon drops the bits, and modelling it as masking would be inventing a gate
    the document never describes.
    """
    spsr = bool(word & 1 << 22)
    held = cpu.registers.saved() if spsr else cpu.registers.cpsr
    if held is None:
        return
    if whole and cpu.mode.privileged:
        updated = value & WORD_MASK
    else:
        updated = (held & ~FLAGS_MASK & WORD_MASK) | (value & FLAGS_MASK)
    if spsr:
        cpu.registers.save(updated)
    else:
        cpu.registers.cpsr = updated


def _finish(cpu: Cpu, register_shift: bool) -> None:
    """The last cycle of a data operation, which is not the same access either way.

    Table 5 gives the plain form one row, an opcode fetch at `pc+8`. The
    register-specified shift form gets two, and its second row drives `pc+12`
    with `Nopc` HIGH and no data, because the fetch already happened in the row
    before it.
    """
    if register_shift:
        cpu.spend(SEQUENTIAL, cpu.registers.pc + 12, nopc=1)
    else:
        cpu.prefetch(SEQUENTIAL, cpu.registers.pc + 8)
    cpu.advance()


def data_processing(cpu: Cpu, word: int) -> None:
    """Table 5, in all four of its shapes."""
    opcode = word >> 21 & 0xF
    setting = bool(word & 1 << 20)
    destination = word >> 12 & 0xF

    if opcode in NO_RESULT and not setting and _psr_transfer(cpu, word):
        _finish(cpu, register_shift=False)
        return

    second, shifter_carry, register_shift = _operand_two(cpu, word)
    if register_shift:
        cpu.prefetch(INTERNAL, cpu.registers.pc + 8)

    if opcode in NO_RESULT and setting and destination == 15:
        _restore_from_saved(cpu)
        _finish(cpu, register_shift)
        return

    first = cpu.read_register(word >> 16 & 0xF, register_shift=register_shift)
    held = alu(opcode, first, second, psr.flag(cpu.registers.cpsr, psr.C_BIT))
    if opcode in LOGICAL:
        held = _logical(held.result, shifter_carry)
        if opcode in NO_RESULT:
            held = Outcome(held.result, held.n, held.z, held.c, held.v, False, False)

    if setting and destination != 15:
        cpu.set_flags(held.n, held.z, held.c, held.v if held.touches_v else _v(cpu))
    if not held.writes:
        _finish(cpu, register_shift)
        return
    if destination == 15:
        _to_counter(cpu, held.result, setting)
        return
    cpu.registers.write(destination, held.result)
    _finish(cpu, register_shift)


def _v(cpu: Cpu) -> bool:
    return psr.flag(cpu.registers.cpsr, psr.V_BIT)


def _restore_from_saved(cpu: Cpu) -> None:
    """The form section 7.3.6 describes, which earlier parts spelled TEQP.

    Its effect is to move `SPSR_<mode>` to the CPSR in a privileged mode, and to
    do nothing in User mode. The datasheet names TEQP alone; the encoding class
    covers all four of the opcodes that set flags without writing a result, and
    that widening is recorded in divergences.json with the corpus behind it.
    """
    saved = cpu.registers.saved()
    if saved is not None:
        cpu.registers.cpsr = saved


def _to_counter(cpu: Cpu, value: int, setting: bool) -> None:
    """Writing the result to R15, which invalidates the pipeline.

    Section 7.3.4: with the S flag set the SPSR of the current mode is moved to
    the CPSR as well, which is what makes a return from an exception restore both
    the counter and the status in one instruction.
    """
    if setting:
        _restore_from_saved(cpu)
    cpu.prefetch(NONSEQUENTIAL, cpu.registers.pc + 8)
    cpu.registers.pc = value & WORD_MASK
    cpu.prefetch(SEQUENTIAL, cpu.registers.pc)
    cpu.prefetch(SEQUENTIAL, cpu.registers.pc + 4)


def multiply(cpu: Cpu, word: int) -> None:
    """Table 6, with `m` from the Booth bands rather than from a loop."""
    destination = word >> 16 & 0xF
    accumulate = bool(word & 1 << 21)
    setting = bool(word & 1 << 20)
    multiplicand = cpu.registers.read(word & 0xF)
    multiplier = cpu.registers.read(word >> 8 & 0xF)
    addend = cpu.registers.read(word >> 12 & 0xF) if accumulate else 0

    cycles = booth_cycles(multiplier)
    cpu.prefetch(INTERNAL, cpu.registers.pc + 8)
    for _ in range(cycles - 1):
        cpu.spend(INTERNAL, cpu.registers.pc + 12, nopc=1)

    if destination == (word & 0xF):
        result = 0 if not accumulate else addend
    else:
        result = (multiplicand * multiplier + addend) & WORD_MASK
    cpu.registers.write(destination, result)
    if setting:
        cpu.set_flags(
            bool(result & SIGN),
            result == 0,
            _meaningless_carry(cpu, multiplicand, multiplier),
            _v(cpu),
        )
    cpu.spend(SEQUENTIAL, cpu.registers.pc + 12, nopc=1)
    cpu.advance()


__all__ = ["Outcome", "alu", "booth_cycles", "data_processing", "immediate", "multiply"]

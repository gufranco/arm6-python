from __future__ import annotations

import random
from typing import TYPE_CHECKING

from arm6 import psr
from arm6.bus import INTERNAL, NONSEQUENTIAL, SEQUENTIAL
from arm6.shifter import by_amount, by_register

if TYPE_CHECKING:  # pragma: no cover
    from arm6.core import Cpu

WORD_MASK = 0xFFFFFFFF

SIGN = 0x80000000

LOGICAL = frozenset({0b0000, 0b0001, 0b1000, 0b1001, 0b1100, 0b1101, 0b1110, 0b1111})

NO_RESULT = frozenset({0b1000, 0b1001, 0b1010, 0b1011})

MAX_BOOTH = 16


class Outcome:
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


def booth_cycles(multiplier: int) -> int:
    return min(MAX_BOOTH, ((multiplier & WORD_MASK).bit_length() + 2) // 2)


def _add(first: int, second: int, carry_in: bool) -> Outcome:
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
    rotate = (word >> 8 & 0xF) * 2
    value = word & 0xFF
    if rotate == 0:
        return value, carry
    value = (value >> rotate | value << (32 - rotate)) & WORD_MASK
    return value, bool(value & SIGN)


def _meaningless_carry(cpu: Cpu, first: int, second: int) -> bool:
    return bool(random.Random((cpu.seed << 8) ^ first ^ (second << 1)).getrandbits(1))


def _operand_two(cpu: Cpu, word: int) -> tuple[int, bool, bool]:
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


def _write_psr(cpu: Cpu, word: int, value: int, whole: bool) -> None:
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
    if register_shift:
        cpu.spend(SEQUENTIAL, cpu.registers.pc + 12, nopc=1)
    else:
        cpu.prefetch(SEQUENTIAL, cpu.registers.pc + 8)
    cpu.advance()


def data_processing(cpu: Cpu, word: int) -> None:
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
    saved = cpu.registers.saved()
    if saved is not None:
        cpu.registers.cpsr = saved


def _to_counter(cpu: Cpu, value: int, setting: bool) -> None:
    if setting:
        _restore_from_saved(cpu)
    cpu.prefetch(NONSEQUENTIAL, cpu.registers.pc + 8)
    cpu.registers.pc = value & WORD_MASK
    cpu.prefetch(SEQUENTIAL, cpu.registers.pc)
    cpu.prefetch(SEQUENTIAL, cpu.registers.pc + 4)


def multiply(cpu: Cpu, word: int) -> None:
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

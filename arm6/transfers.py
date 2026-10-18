from __future__ import annotations

from typing import TYPE_CHECKING

from arm6 import psr
from arm6.bus import INTERNAL, NONSEQUENTIAL, SEQUENTIAL
from arm6.errors import Arm6Error
from arm6.shifter import by_amount

if TYPE_CHECKING:  # pragma: no cover
    from arm6.core import Cpu

WORD_MASK = 0xFFFFFFFF

PREFETCH = 8

STORED_COUNTER_OFFSET = 12


class EmptyRegisterList(Arm6Error):
    __slots__ = ()


class NoCoprocessor(Arm6Error):
    __slots__ = ()


class UnspecifiedEncoding(Arm6Error):
    __slots__ = ()


def branch_target(pc: int, word: int) -> int:
    offset = word & 0x00FFFFFF
    if offset & 0x00800000:
        offset -= 0x01000000
    return (pc + PREFETCH + (offset << 2)) & WORD_MASK


def registers_in(mask: int) -> tuple[int, ...]:
    return tuple(one for one in range(16) if mask >> one & 1)


def rotate_load(value: int, address: int) -> int:
    turn = (address & 0b11) * 8
    if turn == 0:
        return value & WORD_MASK
    return (value >> turn | value << (32 - turn)) & WORD_MASK


def offset_address(base: int, offset: int, up: bool) -> int:
    return (base + offset if up else base - offset) & WORD_MASK


def stored_counter(pc: int) -> int:
    return (pc + STORED_COUNTER_OFFSET) & WORD_MASK


def branch(cpu: Cpu, word: int) -> None:
    target = branch_target(cpu.registers.pc, word)
    cpu.prefetch(NONSEQUENTIAL, cpu.registers.pc + PREFETCH)
    if word & 1 << 24:
        cpu.registers.write(14, (cpu.registers.pc + 4) & WORD_MASK)
    cpu.registers.pc = target
    cpu.prefetch(SEQUENTIAL, target)
    cpu.prefetch(SEQUENTIAL, (target + 4) & WORD_MASK)


def _transfer_offset(cpu: Cpu, word: int) -> int:
    if not word & 1 << 25:
        return word & 0xFFF
    value, _ = by_amount(
        word >> 5 & 0b11,
        cpu.registers.read(word & 0xF),
        word >> 7 & 0x1F,
        psr.flag(cpu.registers.cpsr, psr.C_BIT),
    )
    return value


def single_transfer(cpu: Cpu, word: int) -> None:
    pre = bool(word & 1 << 24)
    up = bool(word & 1 << 23)
    byte = bool(word & 1 << 22)
    write_back = bool(word & 1 << 21)
    load = bool(word & 1 << 20)
    base_index = word >> 16 & 0xF
    destination = word >> 12 & 0xF

    base = cpu.read_register(base_index)
    offset = _transfer_offset(cpu, word)
    address = offset_address(base, offset, up) if pre else base
    written = offset_address(base, offset, up)

    cpu.prefetch(NONSEQUENTIAL, cpu.registers.pc + PREFETCH)
    if load:
        if (pre and write_back) or not pre:
            cpu.registers.write(base_index, written)
        _load_register(cpu, word, address, destination, byte)
    else:
        value = (
            stored_counter(cpu.registers.pc)
            if destination == 15
            else cpu.registers.read(destination)
        )
        cpu.settle()
        if byte:
            cpu.memory.write_byte(address, value & 0xFF)
        else:
            cpu.memory.write_word(address, value)
        cpu.spend(
            NONSEQUENTIAL,
            address,
            nopc=1,
            nbw=0 if byte else 1,
            nrw=1,
            data=value,
        )
    if not load and ((pre and write_back) or not pre):
        cpu.registers.write(base_index, written)
    if not (load and destination == 15):
        cpu.advance()


def _load_register(cpu: Cpu, word: int, address: int, destination: int, byte: bool) -> None:
    cpu.settle()
    if byte:
        value = cpu.memory.read_byte(address)
    else:
        value = rotate_load(cpu.memory.read_word(address), address)
    cpu.spend(INTERNAL, address, nopc=1, nbw=0 if byte else 1, data=value)
    if destination == 15:
        cpu.spend(NONSEQUENTIAL, cpu.registers.pc + 12, nopc=1)
        cpu.registers.pc = value & WORD_MASK
        cpu.prefetch(SEQUENTIAL, cpu.registers.pc)
        cpu.prefetch(SEQUENTIAL, (cpu.registers.pc + 4) & WORD_MASK)
        return
    cpu.registers.write(destination, value)
    cpu.spend(SEQUENTIAL, cpu.registers.pc + 12, nopc=1)


def block_transfer(cpu: Cpu, word: int) -> None:
    pre = bool(word & 1 << 24)
    up = bool(word & 1 << 23)
    force_user = bool(word & 1 << 22)
    write_back = bool(word & 1 << 21)
    load = bool(word & 1 << 20)
    base_index = word >> 16 & 0xF
    listed = registers_in(word & 0xFFFF)
    if not listed:
        raise EmptyRegisterList(
            "the register list should not be empty: section 7.9 states that "
            "restriction and does not say what the part does when it is broken"
        )

    base = cpu.read_register(base_index)
    count = len(listed)
    lowest = base - count * 4 if not up else base
    start = lowest + 4 if (pre and up) or (not pre and not up) else lowest
    addresses = [(start + one * 4) & WORD_MASK for one in range(count)]
    written = offset_address(base, count * 4, up)

    cpu.prefetch(NONSEQUENTIAL, cpu.registers.pc + PREFETCH)
    if load:
        _load_many(cpu, listed, addresses, force_user)
    else:
        _store_many(cpu, listed, addresses, force_user, base_index, written if write_back else None)
    if write_back and not (load and base_index in listed):
        cpu.registers.write(base_index, written)
    if not (load and 15 in listed):
        cpu.advance()


def _bank(cpu: Cpu, index: int, force_user: bool, value: int | None = None) -> int:
    if not force_user or index < 8:
        if value is None:
            return cpu.registers.read(index)
        cpu.registers.write(index, value)
        return value
    held = cpu.registers.cpsr
    cpu.registers.cpsr = psr.with_mode(held, psr.MODES["usr32"])
    try:
        if value is None:
            return cpu.registers.read(index)
        cpu.registers.write(index, value)
        return value
    finally:
        cpu.registers.cpsr = held


def _load_many(cpu: Cpu, listed: tuple[int, ...], addresses: list[int], force_user: bool) -> None:
    cpu.settle()
    values = [cpu.memory.read_word(one) for one in addresses]
    last = len(listed) - 1
    for place, (index, address) in enumerate(zip(listed, addresses, strict=True)):
        kind = INTERNAL if place == last else SEQUENTIAL
        cpu.spend(kind, address, nopc=1, data=values[place])
        if index == 15:
            continue
        _bank(cpu, index, force_user and 15 not in listed, values[place])
    if 15 in listed:
        cpu.spend(NONSEQUENTIAL, cpu.registers.pc + 12, nopc=1)
        if force_user:
            saved = cpu.registers.saved()
            if saved is not None:
                cpu.registers.cpsr = saved
        cpu.registers.pc = values[listed.index(15)] & WORD_MASK
        cpu.prefetch(SEQUENTIAL, cpu.registers.pc)
        cpu.prefetch(SEQUENTIAL, (cpu.registers.pc + 4) & WORD_MASK)
        return
    cpu.spend(SEQUENTIAL, cpu.registers.pc + 12, nopc=1)


def _store_many(
    cpu: Cpu,
    listed: tuple[int, ...],
    addresses: list[int],
    force_user: bool,
    base_index: int,
    written: int | None,
) -> None:
    last = len(listed) - 1
    for place, (index, address) in enumerate(zip(listed, addresses, strict=True)):
        if index == 15:
            value = stored_counter(cpu.registers.pc)
        elif index == base_index and place > 0 and written is not None:
            value = written
        else:
            value = _bank(cpu, index, force_user)
        cpu.settle()
        cpu.memory.write_word(address, value)
        kind = NONSEQUENTIAL if place == last else SEQUENTIAL
        cpu.spend(kind, address, nopc=1, nrw=1, data=value)


def swap(cpu: Cpu, word: int) -> None:
    byte = bool(word & 1 << 22)
    base = cpu.registers.read(word >> 16 & 0xF)
    destination = word >> 12 & 0xF
    source = cpu.registers.read(word & 0xF)

    cpu.prefetch(NONSEQUENTIAL, cpu.registers.pc + PREFETCH)
    cpu.settle()
    held = cpu.memory.read_byte(base) if byte else rotate_load(cpu.memory.read_word(base), base)
    cpu.spend(NONSEQUENTIAL, base, nopc=1, nbw=0 if byte else 1, lock=1, data=held)
    cpu.settle()
    if byte:
        cpu.memory.write_byte(base, source & 0xFF)
    else:
        cpu.memory.write_word(base, source)
    cpu.spend(INTERNAL, base, nopc=1, nbw=0 if byte else 1, nrw=1, lock=1, data=source)
    cpu.registers.write(destination, held)
    cpu.spend(SEQUENTIAL, cpu.registers.pc + 12, nopc=1)
    cpu.advance()


def software_interrupt(cpu: Cpu, word: int) -> None:
    cpu.take("software interrupt", "svc32", cpu.registers.pc + 4)


def undefined(cpu: Cpu, word: int) -> None:
    cpu.spend(INTERNAL, cpu.registers.pc + PREFETCH, nopc=0)
    cpu.take("undefined", "und32", cpu.registers.pc + 4)


def coprocessor(cpu: Cpu, word: int) -> None:
    undefined(cpu, word)


def unspecified(cpu: Cpu, word: int) -> None:
    raise UnspecifiedEncoding(
        f"0x{word:08X} matches no row of Figure 28. The note beneath that figure says "
        "such codes do not take the undefined instruction trap and does not say what "
        "they do, and Application Note 11 refers the answer to the ARM2aS macrocell, "
        "whose data book is not pinned here."
    )

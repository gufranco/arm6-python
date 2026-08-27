"""Everything that moves a word: branches, loads, stores, swaps and traps.

Two of the rules here are easy to state and easy to get one word wrong.

Whenever R15 is stored to memory the stored value is the address of the
instruction plus twelve, not plus eight. The datasheet says so twice, once for
STR and once for STM, and it is the one place the prefetch offset is twelve
without a register-specified shift being involved.

An unaligned word load does not fault and does not truncate. The word is fetched
from the aligned address and then rotated so that the addressed byte occupies
bits 0 to 7, which means a load from an address ending in one returns all four
bytes in a different order rather than three bytes and a gap.

The coprocessor rows share one executor because, with no coprocessor attached,
they share one outcome. Section 10.15 says a coprocessor which cannot perform an
instruction must leave `cpa` and `cpb` HIGH and that this causes the undefined
instruction trap to be taken. Nothing is attached here, so all three rows take it.
"""

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
"""What a store of R15 puts in memory: the instruction's address plus twelve."""


class EmptyRegisterList(Arm6Error):
    """An LDM or STM naming no registers, which the datasheet forbids.

    Section 7.9 states one restriction and this is it: the register list should
    not be empty. What the silicon does with an empty one is not stated, so this
    refuses rather than choosing. The published corpus carries five such cases and
    they are filtered out for the same reason: both parts leave it undefined, so
    agreeing about it would prove nothing.
    """

    __slots__ = ()


class NoCoprocessor(Arm6Error):
    """Reserved for a board that attaches one, which this package does not model."""

    __slots__ = ()


class UnspecifiedEncoding(Arm6Error):
    """An encoding the datasheet says does not trap and does not describe.

    The note beneath Figure 28 gives a multiply with bit 5 or bit 6 set as the
    example and says such codes shall not be used because their action may change.
    Application Note 11 says the behaviour is the ARM2aS macrocell's, and the data
    book describing that macrocell is not pinned here. So this refuses rather than
    inventing an answer, and the refusal says which encoding it was.
    """

    __slots__ = ()


def branch_target(pc: int, word: int) -> int:
    """Where a branch goes: the offset, shifted, sign extended, added to `pc+8`.

    The offset takes account of the prefetch, which is why the base is the
    instruction's address plus two words rather than the address itself.
    """
    offset = word & 0x00FFFFFF
    if offset & 0x00800000:
        offset -= 0x01000000
    return (pc + PREFETCH + (offset << 2)) & WORD_MASK


def registers_in(mask: int) -> tuple[int, ...]:
    """The registers a block transfer names, lowest first.

    The order is the hardware's rather than a convenience: registers are
    transferred lowest to highest with the lowest going to the lowest address,
    and R15 is always last, which is what makes an aborted LDM leave the counter
    intact.
    """
    return tuple(one for one in range(16) if mask >> one & 1)


def rotate_load(value: int, address: int) -> int:
    """An unaligned word load, rotated so the addressed byte is at the bottom."""
    turn = (address & 0b11) * 8
    if turn == 0:
        return value & WORD_MASK
    return (value >> turn | value << (32 - turn)) & WORD_MASK


def offset_address(base: int, offset: int, up: bool) -> int:
    return (base + offset if up else base - offset) & WORD_MASK


def stored_counter(pc: int) -> int:
    return (pc + STORED_COUNTER_OFFSET) & WORD_MASK


def branch(cpu: Cpu, word: int) -> None:
    """Table 4, in three cycles, whether or not the link bit is set."""
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
    """Tables 7 and 8: one word or one byte, with the base optionally written back.

    The order of the two writes is the datasheet's rather than a choice. Section
    10.4: the data is fetched during the second cycle and the base modification is
    performed during that cycle, and during the third cycle the data is
    transferred to the destination register. So when the destination and the base
    are the same register the loaded value wins, because it is written a cycle
    later. Section 10.5 gives the mirror case for a store: the base modification
    and the write to memory happen in the same cycle, so a store of its own base
    puts the unmodified value out.
    """
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
    """Tables 9 and 10: any subset of the registers, lowest to lowest address."""
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
    """Read or write a register, optionally through the user bank.

    The S bit on a block transfer without R15 in the list makes the transfer use
    the user mode registers rather than the current mode's, which is what lets a
    privileged mode save a user process's state.
    """
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
    """Store each register named, with the base a special case the datasheet states.

    Section 7.7.6: the base is written back at the end of the second cycle, and
    the first register is written out at the start of it. So a store that
    includes the base stores the unchanged value when the base is first in the
    transfer order and the modified value when it is second or later. The order
    is by register number rather than by anything the instruction chooses, so
    which of the two applies follows from the list alone.
    """
    last = len(listed) - 1
    for place, (index, address) in enumerate(zip(listed, addresses, strict=True)):
        if index == 15:
            value = stored_counter(cpu.registers.pc)
        elif index == base_index and place > 0 and written is not None:
            value = written
        else:
            value = _bank(cpu, index, force_user)
        cpu.memory.write_word(address, value)
        kind = NONSEQUENTIAL if place == last else SEQUENTIAL
        cpu.spend(kind, address, nopc=1, nrw=1, data=value)


def swap(cpu: Cpu, word: int) -> None:
    """Table 11: a read and a write locked together, with `lock` HIGH between them."""
    byte = bool(word & 1 << 22)
    base = cpu.registers.read(word >> 16 & 0xF)
    destination = word >> 12 & 0xF
    source = cpu.registers.read(word & 0xF)

    cpu.prefetch(NONSEQUENTIAL, cpu.registers.pc + PREFETCH)
    held = cpu.memory.read_byte(base) if byte else rotate_load(cpu.memory.read_word(base), base)
    cpu.spend(NONSEQUENTIAL, base, nopc=1, nbw=0 if byte else 1, lock=1, data=held)
    if byte:
        cpu.memory.write_byte(base, source & 0xFF)
    else:
        cpu.memory.write_word(base, source)
    cpu.spend(INTERNAL, base, nopc=1, nbw=0 if byte else 1, nrw=1, lock=1, data=source)
    cpu.registers.write(destination, held)
    cpu.spend(SEQUENTIAL, cpu.registers.pc + 12, nopc=1)
    cpu.advance()


def software_interrupt(cpu: Cpu, word: int) -> None:
    """Table 12: the return address is the SWI's own address plus four."""
    cpu.take("software interrupt", "svc32", cpu.registers.pc + 4)


def undefined(cpu: Cpu, word: int) -> None:
    """Table 18: one internal cycle offering the instruction, then the trap.

    The first cycle is the coprocessor handshake. `Ncpi` goes LOW, no coprocessor
    drives `cpa` or `cpb` LOW, and the trap follows, which is why the undefined
    instruction costs one cycle more than an exception entry does.
    """
    cpu.spend(INTERNAL, cpu.registers.pc + PREFETCH, nopc=0)
    cpu.take("undefined", "und32", cpu.registers.pc + 4)


def coprocessor(cpu: Cpu, word: int) -> None:
    """All three coprocessor rows, with none attached.

    Section 10.15: a coprocessor which cannot perform an instruction must not
    drive `cpa` or `cpb` LOW, and they remain HIGH, causing the undefined
    instruction trap to be taken. That is what an absent coprocessor looks like
    on this bus, so the outcome is the same as an undefined instruction rather
    than a special case.
    """
    undefined(cpu, word)


def unspecified(cpu: Cpu, word: int) -> None:
    """An encoding outside Figure 28 that the datasheet says does not trap."""
    raise UnspecifiedEncoding(
        f"0x{word:08X} matches no row of Figure 28. The note beneath that figure says "
        "such codes do not take the undefined instruction trap and does not say what "
        "they do, and Application Note 11 refers the answer to the ARM2aS macrocell, "
        "whose data book is not pinned here."
    )

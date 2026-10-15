from __future__ import annotations

import json
import struct
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from arm6 import psr  # noqa: E402
from arm6.core import Cpu  # noqa: E402
from arm6.errors import Arm6Error  # noqa: E402
from arm6.memory import Memory  # noqa: E402

MAGIC = 0xD33DBAE0

STATE_WORDS = 40

CPSR = 31

SPSR_AT = 32

SPSR_ORDER = ("fiq", "svc", "abt", "irq", "und")

FIQ_LOW_AT = 16

BANKS_AT = {"fiq": 21, "svc": 23, "abt": 25, "irq": 27, "und": 29}

PREFETCH = 8

WHOLE_FILES = {
    "arm_bx": "no such row in Figure 28",
    "arm_ldrh_strh": "no such row in Figure 28",
    "arm_ldrsb_ldrsh": "no such row in Figure 28",
    "arm_mull_mlal": "no such row in Figure 28",
    "arm_cdp": "no coprocessor attached",
    "arm_mcr_mrc": "no coprocessor attached",
    "arm_stc_ldc": "no coprocessor attached",
}

ARM_FILES = (
    "arm_b_bl",
    "arm_bx",
    "arm_cdp",
    "arm_data_proc_immediate",
    "arm_data_proc_immediate_shift",
    "arm_data_proc_register_shift",
    "arm_ldm_stm",
    "arm_ldr_str_immediate_offset",
    "arm_ldr_str_register_offset",
    "arm_ldrh_strh",
    "arm_ldrsb_ldrsh",
    "arm_mcr_mrc",
    "arm_mrs",
    "arm_msr_imm",
    "arm_msr_reg",
    "arm_mul_mla",
    "arm_mull_mlal",
    "arm_stc_ldc",
    "arm_swi",
    "arm_swp",
)

SYSTEM_MODE = 0b11111

EXAMPLES = 5


class NotACorpus(Exception): ...


class Case(NamedTuple):
    initial: tuple[int, ...]
    final: tuple[int, ...]
    reads: tuple[tuple[int, int, int], ...]
    opcode: int
    base: int


class Tally:
    def __init__(self) -> None:
        self.files = 0
        self.compared = 0
        self.disagreed = 0
        self.refused = 0
        self.excluded: dict[str, int] = {}
        self.examples: list[str] = []

    def leave_out(self, why: str) -> None:
        self.excluded[why] = self.excluded.get(why, 0) + 1


def pinned() -> dict[str, Any]:
    held: dict[str, Any] = json.loads((ROOT / "conformance" / "suites.json").read_text())
    return held


def cases_in(data: bytes) -> Iterator[Case]:
    magic, _count = struct.unpack_from("<II", data, 0)
    if magic != MAGIC:
        raise NotACorpus(f"0x{magic:08X} is not the magic these files open with")
    at = 8
    while at < len(data):
        (size,) = struct.unpack_from("<I", data, at)
        end = at + size
        inner = at + 4
        blocks: dict[int, tuple[int, ...]] = {}
        while inner < end:
            block, kind = struct.unpack_from("<II", data, inner)
            blocks[kind] = struct.unpack_from(f"<{(block - 8) // 4}I", data, inner + 8)
            inner += block
        yield _case(blocks)
        at = end


def _case(blocks: dict[int, tuple[int, ...]]) -> Case:
    transactions = blocks.get(3, (0,))
    reads = []
    for one in range(transactions[0]):
        kind, size, address, held, _cycle, _access = transactions[1 + one * 6 : 7 + one * 6]
        if kind != 2:
            reads.append((size, address, held))
    tail = blocks.get(4, (0, 0))
    return Case(
        initial=blocks[1],
        final=blocks[2],
        reads=tuple(reads),
        opcode=tail[0],
        base=tail[1],
    )


MEANINGLESS_CARRY = 1 << 29

RESERVED_ON_A_PSR_WRITE = 0x0FFFFF00


def _not_comparable(word: int) -> int:
    if word & 0x0FC000F0 == 0x00000090 and word & 1 << 20:
        return MEANINGLESS_CARRY
    if word & 0x0DBFF000 == 0x0128F000 or word & 0x0FBFFFF0 == 0x0129F000:
        return RESERVED_ON_A_PSR_WRITE
    return 0


def dropped(stem: str) -> str | None:
    return WHOLE_FILES.get(stem)


def excluded(case: Case, stem: str) -> str | None:
    status = case.initial[CPSR]
    if status & psr.MODE_MASK == SYSTEM_MODE:
        return "system mode"
    if status >> 5 & 1:
        return "bit 5 of the CPSR set"
    if stem == "arm_mul_mla":
        if case.opcode & 0x0FC000F0 != 0x00000090:
            return "undefined multiply encoding"
        if case.opcode >> 16 & 0xF == case.opcode & 0xF:
            return "Rd equals Rm"
    if stem == "arm_ldm_stm" and case.opcode & 0xFFFF == 0:
        return "empty register list"
    if psr.mode_for(case.final[CPSR]) is None:
        return "ends in a mode ARM60 does not have"
    if _writes_the_counter_with_the_flag(case) and not psr.mode_of(status).privileged:
        return "S bit with R15 as destination in a user mode"
    return _forbidden(case, stem, psr.mode_of(status).privileged)


def _fields(word: int) -> tuple[int, int, int, int]:
    return word >> 16 & 0xF, word >> 12 & 0xF, word >> 8 & 0xF, word & 0xF


def _forbidden(case: Case, stem: str, privileged: bool) -> str | None:
    word = case.opcode
    rn, rd, rs, rm = _fields(word)
    if stem == "arm_mul_mla" and 15 in (rn, rd, rs, rm):
        return "R15 as a multiply operand"
    if stem == "arm_swp" and 15 in (rn, rd, rm):
        return "R15 as a swap operand"
    if stem == "arm_ldm_stm":
        if rn == 15:
            return "R15 as the base of a block transfer"
        if word & 1 << 22:
            if not privileged:
                return "the S bit of a block transfer set outside a privileged mode"
            if word & 1 << 21:
                return "base write-back with the S bit of a block transfer set"
    if stem.startswith("arm_ldr_str"):
        if word & 1 << 25 and rm == 15:
            return "R15 as a transfer's register offset"
        if rn == 15 and (word & 1 << 21 or not word & 1 << 24):
            return "write-back onto R15 as a transfer's base"
        if not word & 1 << 24 and word & 1 << 25 and rm == rn:
            return "a post-indexed transfer whose offset register is its base"
    if stem == "arm_mrs":
        if rd == 15:
            return "R15 as the destination of a PSR read"
        if word & 1 << 22 and not privileged:
            return "an SPSR reached from a user mode"
    if stem.startswith("arm_msr"):
        if rn not in (0b1000, 0b1001):
            return "an MSR field mask Figure 14 does not print"
        if word & 1 << 25 and rn == 0b1001:
            return "an eight bit immediate written into the whole PSR"
        if not word & 1 << 25 and rm == 15:
            return "R15 as the source of a PSR write"
        if word & 1 << 22 and not privileged:
            return "an SPSR reached from a user mode"
        if rn == 0b1001 and not _lands_in_a_thirty_two_bit_mode(case):
            return "a mode the generator's part cannot enter written into a PSR"
    if _register_shift(word) and rs == 15:
        return "R15 as the register holding a shift amount"
    return None


def _visible(case: Case, index: int) -> int:
    mode = psr.mode_of(case.initial[CPSR])
    if index < 8 or index == 15:
        return case.initial[index]
    if index < 13:
        return case.initial[FIQ_LOW_AT + index - 8] if mode.bank == "fiq" else case.initial[index]
    at = BANKS_AT.get(mode.bank)
    return case.initial[index] if at is None else case.initial[at + index - 13]


def _lands_in_a_thirty_two_bit_mode(case: Case) -> bool:
    wanted = _visible(case, case.opcode & 0xF) & psr.MODE_MASK
    found = psr.mode_for(wanted)
    return found is not None and found.wide


def _register_shift(word: int) -> bool:
    return word & 0x0E000010 == 0x00000010


def _writes_the_counter_with_the_flag(case: Case) -> bool:
    word = case.opcode
    if word & 0x0C000000 != 0:
        return False
    return bool(word & 1 << 20) and word >> 12 & 0xF == 15


def _load(case: Case) -> Cpu:
    memory = Memory(fill=0)
    for size, address, held in case.reads:
        if size == 1:
            memory.write_byte(address, held)
        else:
            memory.write_word(address, held)
    memory.write_word(case.base, case.opcode)

    cpu = Cpu("arm60", memory, fill=0)
    cpu.registers.cpsr = case.initial[CPSR]
    cpu.registers.common[:] = list(case.initial[0:8])
    cpu.registers.low[:] = list(case.initial[8:13])
    cpu.registers.fiq_low[:] = list(case.initial[FIQ_LOW_AT : FIQ_LOW_AT + 5])
    cpu.registers.banked["usr"] = [case.initial[13], case.initial[14]]
    for name, at in BANKS_AT.items():
        cpu.registers.banked[name] = [case.initial[at], case.initial[at + 1]]
    for name, at in zip(SPSR_ORDER, range(SPSR_AT, SPSR_AT + 5), strict=True):
        cpu.registers.spsr[name] = case.initial[at]
    cpu.registers.pc = (case.initial[15] - PREFETCH) & 0xFFFFFFFF
    return cpu


def compare(case: Case) -> list[str]:
    cpu = _load(case)
    try:
        cpu.step()
    except Arm6Error as refused:
        return [f"{type(refused).__name__}: {refused}"]

    found = []
    held = list(cpu.registers.common) + list(cpu.registers.low) + cpu.registers.banked["usr"]
    for index in range(15):
        if held[index] != case.final[index]:
            found.append(f"R{index} is 0x{held[index]:08X}, recorded 0x{case.final[index]:08X}")
    for at, one in enumerate(cpu.registers.fiq_low):
        if one != case.final[FIQ_LOW_AT + at]:
            found.append(
                f"R{8 + at}_fiq is 0x{one:08X}, recorded 0x{case.final[FIQ_LOW_AT + at]:08X}"
            )
    for name, at in BANKS_AT.items():
        for offset, one in enumerate(cpu.registers.banked[name]):
            if one != case.final[at + offset]:
                found.append(
                    f"R{13 + offset}_{name} is 0x{one:08X},"
                    f" recorded 0x{case.final[at + offset]:08X}"
                )
    counter = (cpu.registers.pc + PREFETCH) & 0xFFFFFFFF
    if counter != case.final[15]:
        found.append(f"R15 is 0x{counter:08X}, recorded 0x{case.final[15]:08X}")
    mask = 0xFFFFFFFF & ~_not_comparable(case.opcode)
    if cpu.registers.cpsr & mask != case.final[CPSR] & mask:
        found.append(f"CPSR is 0x{cpu.registers.cpsr:08X}, recorded 0x{case.final[CPSR]:08X}")
    for name, at in zip(SPSR_ORDER, range(SPSR_AT, SPSR_AT + 5), strict=True):
        if cpu.registers.spsr[name] & mask != case.final[at] & mask:
            found.append(
                f"SPSR_{name} is 0x{cpu.registers.spsr[name]:08X}, recorded 0x{case.final[at]:08X}"
            )
    return found


def sweep(
    where: Path,
    limit: int | None = None,
    counting: bool = False,
    say: Callable[[str], object] = print,
) -> Tally:
    tally = Tally()
    for path in sorted(where.glob("arm_*.json.bin")):
        stem = path.stem.replace(".json", "")
        why = dropped(stem)
        if why is not None:
            tally.leave_out(f"{stem}: {why}")
            continue
        tally.files += 1
        seen = 0
        for case in cases_in(path.read_bytes()):
            out = excluded(case, stem)
            if out is not None:
                tally.leave_out(out)
                continue
            seen += 1
            if counting:
                tally.compared += 1
                continue
            differ = compare(case)
            tally.compared += 1
            if differ:
                tally.disagreed += 1
                if len(tally.examples) < EXAMPLES:
                    tally.examples.append(
                        f"{stem} 0x{case.opcode:08X} at 0x{case.base:08X}: {differ[0]}"
                    )
            if limit is not None and seen >= limit:
                break
        say(f"  {stem}: {seen:,} usable")
    return tally


def report(tally: Tally) -> list[str]:
    if tally.compared == 0:
        return [
            "  no corpus on this machine, so nothing was compared.",
            "  clone it and pass the path: see the usage at the top of this file.",
        ]
    lines = [
        f"  {tally.files} files, {tally.compared:,} cases compared,"
        f" {tally.disagreed:,} disagreements"
    ]
    for why, count in sorted(tally.excluded.items(), key=lambda one: -one[1]):
        lines.append(f"     left out: {count:,} for {why}")
    lines.extend(f"     ! {one}" for one in tally.examples)
    return lines


def verdict(tally: Tally) -> int:
    return 1 if tally.disagreed else 0


def wanted() -> list[str]:
    return [f"/v1/{one}.json.bin" for one in ARM_FILES if one not in WHOLE_FILES]


def main(argv: Sequence[str] = (), say: Callable[[str], object] = print) -> int:
    rest = list(argv)
    if "--files" in rest:
        for one in wanted():
            say(one)
        return 0
    counting = "--count" in rest
    if counting:
        rest.remove("--count")
    limit = None
    if "--limit" in rest:
        at = rest.index("--limit")
        limit = int(rest[at + 1])
        del rest[at : at + 2]
    where = Path(rest[0]) if rest else Path("ARM7TDMI/v1")
    if not where.is_dir():
        for line in report(Tally()):
            say(line)
        return 0
    tally = sweep(where, limit=limit, counting=counting, say=say)
    for line in report(tally):
        say(line)
    return verdict(tally)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

from __future__ import annotations

from collections.abc import Callable
from typing import Any, override

from arm6 import dataops, decode, psr, transfers
from arm6.bus import NONSEQUENTIAL, SEQUENTIAL, Cycle, CycleType, Recorder
from arm6.errors import RunLimit
from arm6.memory import UNSET_SEED, Memory
from arm6.models import Model, resolve
from arm6.registers import Registers
from arm6.tally import Cycles

WORD_MASK = 0xFFFFFFFF

PREFETCH = 8

PREFETCH_WITH_REGISTER_SHIFT = 12

VECTORS = {
    "reset": 0x00000000,
    "undefined": 0x00000004,
    "software interrupt": 0x00000008,
    "prefetch abort": 0x0000000C,
    "data abort": 0x00000010,
    "irq": 0x00000018,
    "fiq": 0x0000001C,
}

RESET_LOW_CYCLES = 2


class Cpu:
    __slots__ = (
        "_open",
        "bigend",
        "bus",
        "cycles",
        "fiq_line",
        "irq_line",
        "lateabt",
        "memory",
        "model",
        "on_cycle",
        "registers",
        "seed",
        "spent",
        "steps",
        "tally",
    )

    model: Model
    memory: Memory
    registers: Registers
    bus: Recorder
    cycles: int
    steps: int
    spent: Cycles
    tally: Cycles
    seed: int
    bigend: bool
    lateabt: bool
    irq_line: bool
    fiq_line: bool
    on_cycle: Callable[[Cpu], None] | None

    def __init__(
        self,
        model: str,
        memory: Memory | None = None,
        seed: int = UNSET_SEED,
        fill: int | None = None,
        bigend: bool = False,
        lateabt: bool = True,
    ) -> None:
        self.model = resolve(model)
        self.seed = seed
        self.bigend = bigend
        self.lateabt = lateabt
        self.memory = Memory(seed=seed, fill=fill, bigend=bigend) if memory is None else memory
        self.registers = Registers(seed=seed, fill=fill)
        self.bus = Recorder()
        self.cycles = 0
        self.steps = 0
        self.spent = Cycles()
        self.tally = Cycles()
        self.irq_line = False
        self.fiq_line = False
        self.on_cycle = None
        self._open = False

    @override
    def __repr__(self) -> str:
        return f"Cpu({self.model.name!r})"

    @property
    def mode(self) -> psr.Mode:
        return self.registers.mode

    def spend(
        self,
        kind: CycleType,
        address: int,
        nopc: int,
        nbw: int = 1,
        nrw: int = 0,
        lock: int = 0,
        data: int | None = None,
    ) -> Cycle:
        self.settle()
        cycle = Cycle(
            kind,
            address=address,
            nopc=nopc,
            nbw=nbw,
            nrw=nrw,
            ntrans=0 if self.mode.bank == "usr" else 1,
            lock=lock,
            data=data,
        )
        self.bus.add(cycle)
        self._open = True
        return cycle

    def settle(self) -> None:
        if not self._open:
            return
        self._open = False
        self.cycles += 1
        if self.on_cycle is not None:
            self.on_cycle(self)

    def prefetch(self, kind: CycleType, address: int) -> Cycle:
        address &= WORD_MASK
        self.settle()
        return self.spend(kind, address, nopc=0, data=self.memory.read_word(address))

    def reset(self, low_cycles: int = RESET_LOW_CYCLES) -> Cpu:
        low_cycles = max(low_cycles, RESET_LOW_CYCLES)
        self.bus.clear()
        held = self.registers.pc
        for one in range(low_cycles):
            self.prefetch(SEQUENTIAL, held + one * 4)

        undefined = Registers(seed=self.seed ^ 0x9E3779B9)
        self.registers.cpsr = psr.with_mode(self.registers.cpsr, psr.MODES["svc32"])
        self.registers.write(14, undefined.pc)
        self.registers.save(undefined.cpsr)
        self.registers.cpsr = psr.with_flag(self.registers.cpsr, psr.I_BIT, True)
        self.registers.cpsr = psr.with_flag(self.registers.cpsr, psr.F_BIT, True)
        self.enter(VECTORS["reset"])
        self.steps = 0
        self.spent = self.bus.spent()
        self.tally = self.tally + self.spent
        self.settle()
        return self

    def enter(self, vector: int) -> None:
        self.prefetch(NONSEQUENTIAL, self.registers.pc + PREFETCH)
        self.registers.pc = vector
        self.prefetch(SEQUENTIAL, vector)
        self.prefetch(SEQUENTIAL, vector + 4)

    def take(self, name: str, mode: str, link: int, mask_fiq: bool = False) -> None:
        saved = self.registers.cpsr
        self.registers.cpsr = psr.with_mode(saved, psr.MODES[mode])
        self.registers.save(saved)
        self.registers.write(14, link & WORD_MASK)
        self.registers.cpsr = psr.with_flag(self.registers.cpsr, psr.I_BIT, True)
        if mask_fiq:
            self.registers.cpsr = psr.with_flag(self.registers.cpsr, psr.F_BIT, True)
        self.enter(VECTORS[name])

    def flags(self) -> tuple[bool, bool, bool, bool]:
        held = self.registers.cpsr
        return (
            psr.flag(held, psr.N_BIT),
            psr.flag(held, psr.Z_BIT),
            psr.flag(held, psr.C_BIT),
            psr.flag(held, psr.V_BIT),
        )

    def set_flags(self, n: bool, z: bool, c: bool, v: bool) -> None:
        held = self.registers.cpsr
        held = psr.with_flag(held, psr.N_BIT, n)
        held = psr.with_flag(held, psr.Z_BIT, z)
        held = psr.with_flag(held, psr.C_BIT, c)
        held = psr.with_flag(held, psr.V_BIT, v)
        self.registers.cpsr = held

    def passes(self, word: int) -> bool:
        n, z, c, v = self.flags()
        code = word >> 28 & 0xF
        if code < 8:
            return (z, not z, c, not c, n, not n, v, not v)[code]
        return (
            c and not z,
            (not c) or z,
            n == v,
            n != v,
            (not z) and n == v,
            z or n != v,
            True,
            False,
        )[code - 8]

    def read_register(self, index: int, register_shift: bool = False) -> int:
        if index != 15:
            return self.registers.read(index)
        ahead = PREFETCH_WITH_REGISTER_SHIFT if register_shift else PREFETCH
        return (self.registers.pc + ahead) & WORD_MASK

    def advance(self) -> None:
        self.registers.pc = (self.registers.pc + 4) & WORD_MASK

    def step(self) -> int:
        self.bus.clear()
        self.steps += 1
        if self.fiq_line and not psr.flag(self.registers.cpsr, psr.F_BIT):
            self.take("fiq", "fiq32", self.registers.pc + PREFETCH, mask_fiq=True)
        elif self.irq_line and not psr.flag(self.registers.cpsr, psr.I_BIT):
            self.take("irq", "irq32", self.registers.pc + PREFETCH)
        else:
            self.run_one()
        self.spent = self.bus.spent()
        self.tally = self.tally + self.spent
        self.settle()
        return self.spent.total

    def run_one(self) -> None:
        word = self.memory.read_word(self.registers.pc)
        if not self.passes(word):
            self.prefetch(SEQUENTIAL, self.registers.pc + PREFETCH)
            self.advance()
            return
        EXECUTORS[decode.classify(word)](self, word)

    def run_for(self, cycles: int) -> int:
        spent = 0
        while spent < cycles:
            spent += self.step()
        return spent

    def run_until(self, predicate: Callable[[Cpu], bool], limit: int | None = None) -> Cpu:
        taken = 0
        while not predicate(self):
            self.step()
            taken += 1
            if limit is not None and taken >= limit:
                raise RunLimit(f"gave up after {taken} instructions without the predicate holding")
        return self

    def held(self) -> bool:
        return False

    def irq(self, level: bool = True) -> bool:
        self.irq_line = level
        return level and not psr.flag(self.registers.cpsr, psr.I_BIT)

    def fiq(self, level: bool = True) -> bool:
        self.fiq_line = level
        return level and not psr.flag(self.registers.cpsr, psr.F_BIT)


EXECUTORS: dict[str, Any] = {
    decode.DATA_PROCESSING: dataops.data_processing,
    decode.MULTIPLY: dataops.multiply,
    decode.SINGLE_DATA_SWAP: transfers.swap,
    decode.SINGLE_DATA_TRANSFER: transfers.single_transfer,
    decode.UNDEFINED: transfers.undefined,
    decode.BLOCK_DATA_TRANSFER: transfers.block_transfer,
    decode.BRANCH: transfers.branch,
    decode.COPROCESSOR_DATA_TRANSFER: transfers.coprocessor,
    decode.COPROCESSOR_DATA_OPERATION: transfers.coprocessor,
    decode.COPROCESSOR_REGISTER_TRANSFER: transfers.coprocessor,
    decode.SOFTWARE_INTERRUPT: transfers.software_interrupt,
    decode.UNSPECIFIED: transfers.unspecified,
}

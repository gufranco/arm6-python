"""The part: what it holds, what a cycle costs, and how an exception is entered.

Two things here are the datasheet's rather than a modelling choice, and both are
easy to get subtly wrong.

The first is that reset defines and power-on scrambles. Section 6.3.6 says reset
overwrites `R14_svc` and `SPSR_svc` with the current PC and CPSR and then adds
that the value of the saved PC and CPSR is not defined. So construction puts
every register in the state the rail coming up leaves it, including the program
counter, and reset writes exactly the three things the section lists and leaves
everything else holding what it held.

The second is that reset is not free. Section 6.3.6: `Nreset` must be held LOW
for at least two clock cycles, and during that period the part performs dummy
instruction fetches with the address incrementing. Those are real bus cycles and
they appear in the tally.
"""

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
"""How far ahead R15 reads of the instruction using it.

Section 7.3.5: the PC value will be the address of the instruction plus 8 or 12
bytes due to instruction prefetching, 8 when the shift amount is in the
instruction and 12 when a register supplies it.
"""

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
"""Section 6.3.7, in full.

`0x00000014` is absent on purpose: the datasheet reserves it for an address
exception vector which is only operative when the part is configured for a 26-bit
program space, and this package models the 32-bit configuration.
"""

RESET_LOW_CYCLES = 2
"""The minimum the datasheet states, not a figure anybody chose.

`Nreset` must remain LOW for at least two clock cycles. A board that holds it
longer says so, and the dummy fetches during that period are counted either way.
"""


class Cpu:
    """One ARM60, driven by a clock and reporting what it spent.

    `step` returns an integer because that is what every member of this family
    returns and what a host needs to pace anything. The integer is the cycle
    count, which is also the tick count in the one configuration the pin table
    names outright: `Nwait` tied HIGH, one `mclk` per cycle. Any other board makes
    a cycle cost something else, and `spent.ticks(waits)` is where a caller says
    what theirs costs.
    """

    __slots__ = (
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
        """The one place a cycle is spent, so nothing can spend one privately.

        A counter kept in one method and a watcher called from another drift the
        first time somebody adds a cycle to only one of them. Every path that
        costs a cycle comes through here, including the ones that touch no memory.

        `Ntrans` is not an argument. Section 6 gives it as LOW when the processor
        is in user mode, so it follows from the mode rather than from the
        instruction. Table 8 heads an `Ntrans` column and prints no values under
        it, which is a gap in the document rather than a fact about the pin.
        """
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
        self.cycles += 1
        if self.on_cycle is not None:
            self.on_cycle(self)
        return cycle

    def prefetch(self, kind: CycleType, address: int) -> Cycle:
        """An instruction fetch, which is a real access whether or not it is used.

        Every chapter 10 table opens with a fetch from `pc+8`, and most of them
        discard it. A discarded read is still an access, so the read happens and
        the word appears in the record.
        """
        address &= WORD_MASK
        return self.spend(kind, address, nopc=0, data=self.memory.read_word(address))

    def reset(self, low_cycles: int = RESET_LOW_CYCLES) -> Cpu:
        """Section 6.3.6, including what it costs and what it leaves alone.

        The saved PC and CPSR are explicitly not defined, so they are scrambled
        from the seed rather than filled in with whatever is convenient.
        Everything the section does not name keeps what it held, which is the
        difference between a reset and a power-on.
        """
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
        return self

    def enter(self, vector: int) -> None:
        """The three cycles Table 12 gives every exception, reset included.

        Section 10.9 covers software interrupts and exception entry together, and
        the note under Table 12 names reset among the events it describes.
        """
        self.prefetch(NONSEQUENTIAL, self.registers.pc + PREFETCH)
        self.registers.pc = vector
        self.prefetch(SEQUENTIAL, vector)
        self.prefetch(SEQUENTIAL, vector + 4)

    def take(self, name: str, mode: str, link: int, mask_fiq: bool = False) -> None:
        """Enter one exception: bank the status, set the link, then vector.

        The order is the datasheet's. The mode changes first, so the link register
        written and the saved status register written are the new mode's rather
        than the old one's, which is the whole reason those registers are banked.
        """
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
        """Whether the condition field lets this instruction execute.

        Figure 5, in full. `NV` is never, and the datasheet says the class shall
        not be used because it will be redefined in future variants; refusing to
        execute it is what the encoding means today.
        """
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
        """One register, with the prefetch offset R15 carries.

        Section 7.3.5: the PC is 8 bytes ahead when the shift amount is in the
        instruction and 12 bytes ahead when a register supplies it.
        """
        if index != 15:
            return self.registers.read(index)
        ahead = PREFETCH_WITH_REGISTER_SHIFT if register_shift else PREFETCH
        return (self.registers.pc + ahead) & WORD_MASK

    def advance(self) -> None:
        self.registers.pc = (self.registers.pc + 4) & WORD_MASK

    def step(self) -> int:
        """One instruction, and what it cost.

        The interrupt lines are sampled here rather than inside an instruction,
        because both are level-sensitive inputs the part reads at an instruction
        boundary. Section 6.3.8 puts FIQ above IRQ, and both are masked by their
        own bit in the CPSR: unlike the other clocked members of this family,
        ARM60 brings out no line that a flag cannot refuse.
        """
        self.bus.clear()
        if self.fiq_line and not psr.flag(self.registers.cpsr, psr.F_BIT):
            self.take("fiq", "fiq32", self.registers.pc + PREFETCH, mask_fiq=True)
        elif self.irq_line and not psr.flag(self.registers.cpsr, psr.I_BIT):
            self.take("irq", "irq32", self.registers.pc + PREFETCH)
        else:
            self.run_one()
        self.steps += 1
        self.spent = self.bus.spent()
        self.tally = self.tally + self.spent
        return self.spent.total

    def run_one(self) -> None:
        word = self.memory.read_word(self.registers.pc)
        if not self.passes(word):
            self.prefetch(SEQUENTIAL, self.registers.pc + PREFETCH)
            self.advance()
            return
        EXECUTORS[decode.classify(word)](self, word)

    def run_for(self, cycles: int) -> int:
        """A budget, and what was really spent, which usually overshoots.

        An instruction is not divisible, so a host carries the overshoot into the
        next slice rather than discarding it and a long run does not drift.
        """
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
        """Whether the part has stopped advancing the program, which it never has.

        ARM60 has no instruction and no state that stops it. It is a fully static
        design and the clock may be stopped in any part of the cycle, but that is
        the board stopping `mclk` rather than the part stopping itself, and a
        stopped clock is not something the part can report.

        The one place the datasheet describes the part waiting is the coprocessor
        busy-wait, and it waits there only while a coprocessor holds `cpa` LOW
        without committing. Nothing is attached here, so section 10.15 applies
        instead and the instruction takes the undefined trap.
        """
        return False

    def irq(self, level: bool = True) -> bool:
        """Offer the `Nirq` line, and say whether it would be taken.

        A level rather than an event: the datasheet says `Nirq` must be held LOW
        until a suitable response is received, so a request raised and withdrawn
        before the part looks is not taken, which is what a device withdrawing
        its request does.
        """
        self.irq_line = level
        return level and not psr.flag(self.registers.cpsr, psr.I_BIT)

    def fiq(self, level: bool = True) -> bool:
        """Offer the `Nfiq` line, the higher priority of the two.

        Nothing here is unmaskable. Section 6.3.8 puts FIQ above IRQ in priority
        and the F bit still refuses it, which is the shape of this part rather
        than an omission in the package.
        """
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
"""One executor per row of Figure 28, plus the encodings the figure does not cover.

The three coprocessor rows share one executor because, with nothing attached,
they share one outcome: section 10.15 says a coprocessor which cannot perform an
instruction leaves `cpa` and `cpb` HIGH, which takes the undefined instruction
trap.
"""

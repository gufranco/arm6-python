# ARM6

The ARM60 processor in Python, advanced one instruction or one bus cycle at a time, held to the GEC Plessey ARM60 datasheet for every instruction and every cycle it spends, and to a filtered ARM7TDMI corpus for the processor state after each one.

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/arm6-python)](https://github.com/gufranco/arm6-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**424,220** recorded cases compared, **0** disagreements, **62** quoted sentences placed on the page they cite, **1** part, **1,183** tests, **100%** statement and branch coverage, no dependencies

```python
from arm6 import Cpu, Memory

cpu = Cpu("arm60", Memory(image=(0xE3A0002A).to_bytes(4, "little"), fill=0)).reset()

spent = cpu.step()

print(f"{cpu.registers.read(0):#010x} in {spent} cycle, {cpu.spent}")
```

```
0x0000002a in 1 cycle, Cycles(s=1, n=0, i=0, c=0)
```

The image holds one word, `mov R0, #42`. `reset()` points the program counter at address zero, and `step()` runs that one instruction. It cost one sequential cycle, which is what Table 20 gives for a data operation. `spent` holds the cost split into the datasheet's four cycle types: S, N, I and C.

## Install

| Requirement                | Version                                           |
| :------------------------- | :------------------------------------------------ |
| Python                     | 3.12 or newer                                     |
| git                        | Any                                               |
| `pdftoppm` and `tesseract` | Any, and only for `python3 -m conformance.quotes` |

```bash
git clone https://github.com/gufranco/arm6-python.git
cd arm6-python
python3 arm6/doctor.py
```

The package imports nothing outside the standard library. `pip install git+https://github.com/gufranco/arm6-python.git` installs it without a checkout, and adds an `arm6-doctor` command that runs the same doctor.

The doctor checks the machine and the checkout, builds and steps one part, and ends with one line. It exits 0 when every check passes and 1 otherwise. Paste its whole output into any bug report.

```
  5 checks, nothing to report
```

On a machine without `pdftoppm` or `tesseract`, the last line reads `1 of 5 checks did not pass`. Everything except the quote checker still works there.

Releases follow [Semantic Versioning](https://semver.org/) and are cut from the commit history by semantic-release. Every release is tagged and listed on the [releases page](https://github.com/gufranco/arm6-python/releases).

## The interface

`arm6.Cpu(model, memory=None, seed=UNSET_SEED, fill=None, bigend=False, lateabt=True)` builds one part.

| Argument  | Meaning                                                                                                                                        |
| :-------- | :--------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`   | Required. `arm60`, or its alias `arm6`, in any case. There is no default                                                                       |
| `memory`  | Any object with `read_byte`, `write_byte`, `read_word` and `write_word`. Left out, the part builds a `Memory` from `seed`, `fill` and `bigend` |
| `seed`    | Sets the power-on contents of the registers and of a memory the part builds                                                                    |
| `fill`    | A value every register and every unwritten byte starts at instead. `fill=0` gives a quiet start                                                |
| `bigend`  | The `bigend` pin. Passed to a memory the part builds, and ignored when `memory` is supplied                                                    |
| `lateabt` | The `lateabt` pin, kept on the part. The abort pin is not driven, so it changes nothing                                                        |

### Calls

| Call                                 | Effect                                                                                                                                                                                                                           | Returns                         |
| :----------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------ |
| `reset(low_cycles=2)`                | Section 6.3.6: supervisor mode, both interrupt disables set, a fetch from address zero. Holds the reset line for `low_cycles` dummy fetches, never fewer than 2, then spends 3 on exception entry, so the default costs 5 cycles | The part                        |
| `step()`                             | One instruction, or the entry to a pending FIQ or IRQ                                                                                                                                                                            | The cycles it cost, as an `int` |
| `run_for(cycles)`                    | Whole instructions until at least `cycles` have been spent. An instruction is never split, so it may overshoot                                                                                                                   | The cycles spent                |
| `run_until(check, limit=None)`       | Steps while `check(cpu)` is false. Raises `RunLimit` after `limit` instructions                                                                                                                                                  | The part                        |
| `held()`                             | Whether the part has stopped advancing. Nothing stops this part                                                                                                                                                                  | `False`                         |
| `irq(level=True)`, `fiq(level=True)` | Sets the line. The next `step()` takes it when its disable bit is clear                                                                                                                                                          | Whether it would be taken now   |

### State

| Attribute                   | Meaning                                                                                                                                                                                                                                                                          |
| :-------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `model`                     | The `Model` record: `name`, `aliases`, `summary`                                                                                                                                                                                                                                 |
| `memory`                    | The memory object                                                                                                                                                                                                                                                                |
| `registers`                 | The `Registers`: `read(index)`, `write(index, value)`, `pc`, `cpsr`, `saved()`, `save(value)`, `mode`                                                                                                                                                                            |
| `mode`                      | The current `Mode`, read from the CPSR                                                                                                                                                                                                                                           |
| `cycles`                    | Cycles since the part was built, reset included                                                                                                                                                                                                                                  |
| `steps`                     | Instructions since the last reset                                                                                                                                                                                                                                                |
| `spent`                     | The last instruction's cost as `Cycles`                                                                                                                                                                                                                                          |
| `tally`                     | The running total as `Cycles`, kept across resets                                                                                                                                                                                                                                |
| `bus.cycles`                | One `Cycle` per bus cycle of the last instruction: `kind`, `address`, `nopc`, `nbw`, `nrw`, `ntrans`, `lock`, `data`. `kind` is one of the Table 3 cycle types a part with no coprocessor attached drives: N, S or I, with `letter`, `name`, `nmreq`, `seq` and `touches_memory` |
| `irq_line`, `fiq_line`      | The level of each interrupt line                                                                                                                                                                                                                                                 |
| `on_cycle`                  | A callable run at the end of every bus cycle, after that cycle's work, with the part as its argument, or `None`. `Clock` sets it                                                                                                                                                 |
| `seed`, `bigend`, `lateabt` | The constructor arguments                                                                                                                                                                                                                                                        |

```python
from arm6 import Cpu, Memory, RunLimit

words = (0xE3A00000, 0xE2800001, 0xE3500003, 0x1AFFFFFC, 0xEAFFFFFE)
image = b"".join(word.to_bytes(4, "little") for word in words)
cpu = Cpu("arm60", Memory(image=image, fill=0), fill=0).reset()

cpu.run_until(lambda part: part.registers.pc == 0x10, limit=100)
print(cpu.registers.read(0), cpu.steps, cpu.cycles, cpu.tally)

print(cpu.run_for(10), cpu.spent, [row.kind.letter for row in cpu.bus.cycles])

try:
    cpu.run_until(lambda part: part.registers.read(0) == 4, limit=50)
except RunLimit as stopped:
    print(stopped)

print(cpu.held(), cpu.irq(), cpu.fiq(False))
```

```
3 10 19 Cycles(s=16, n=3, i=0, c=0)
12 Cycles(s=2, n=1, i=0, c=0) ['N', 'S', 'S']
gave up after 50 instructions without the predicate holding
False False False
```

The program counts R0 up to 3 and then branches to itself. Ten instructions cost 14 cycles, and the 5 of the reset make 19. `run_for(10)` runs four of the 3-cycle branches and reports 12. Each branch drives one non-sequential fetch and two sequential ones. `irq()` answers `False` because the reset left the I bit set.

### Memory, registers and modes

`arm6.Memory(image=None, seed=UNSET_SEED, fill=None, bigend=False)` is 4 GB of sparse memory. `image` is written from address zero. Every byte nobody wrote reads as `fill`, or as a value derived from `seed` and the address when `fill` is `None`. `read_byte`, `write_byte`, `read_word` and `write_word` are the calls. A word access ignores the two low address bits. `written` maps every written address to its byte.

`arm6.Registers` holds 31 general registers and 6 status registers. `read(15)` returns the program counter with the two low bits cleared.

```python
from arm6 import MODES, UNSET_SEED, VECTORS, Cpu, Memory

little = Memory(image=b"\x78\x56\x34\x12", fill=0)
big = Memory(image=b"\x78\x56\x34\x12", fill=0, bigend=True)
print(f"{little.read_word(0):#010x} {big.read_word(0):#010x} {little.read_byte(3):#04x}")

little.write_word(0x2002, 0xCAFEF00D)
print(f"{little.read_word(0x2000):#010x}", [hex(one) for one in sorted(little.written)[-4:]])
print(Memory(seed=1).read_byte(0x100) != Memory(seed=2).read_byte(0x100), hex(UNSET_SEED))

cpu = Cpu("arm60", fill=0).reset()
print(f"{cpu.registers.cpsr:#010x}", cpu.mode.name, cpu.mode.privileged)
print(cpu.registers.general_count(), cpu.registers.status_count())

print(VECTORS["irq"], VECTORS["fiq"])
print([name for name, mode in MODES.items() if not mode.wide])
```

```
0x12345678 0x78563412 0x12
0xcafef00d ['0x2000', '0x2001', '0x2002', '0x2003']
True 0x5a5a5a5a
0x000000d3 svc32 True
31 6
24 28
['usr26', 'fiq26', 'irq26', 'svc26']
```

The same four bytes read as two different words once `bigend` is set. A word written at 0x2002 lands at 0x2000. Two seeds give two different power-on bytes. After a reset the CPSR holds `0xd3`: supervisor mode with the I and F bits set.

| Name              | Content                                                                                                                                                                                                  |
| :---------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `arm6.MODES`      | The ten `Mode` records, keyed by name: `usr32`, `fiq32`, `irq32`, `svc32`, `abt32`, `und32`, and the 26-bit `usr26`, `fiq26`, `irq26`, `svc26`. Each has `bits`, `wide`, `privileged`, `bank` and `spsr` |
| `arm6.VECTORS`    | The seven exception vectors by name, from `reset` at 0x00 to `fiq` at 0x1C                                                                                                                               |
| `arm6.UNSET_SEED` | The seed used when none is given                                                                                                                                                                         |

### Catalogue and errors

| Name                       | Content                                                                                                                                                |
| :------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `arm6.MODELS`              | The one `Model` record, keyed by `arm60`                                                                                                               |
| `arm6.Model`               | A catalogue entry. It refuses every attribute write                                                                                                    |
| `arm6.Arm6Error`           | The base of every error below                                                                                                                          |
| `arm6.UnknownModelError`   | Raised by `Cpu` for a name no model goes by, and for an empty name. The message lists every name accepted                                              |
| `arm6.RunLimit`            | Raised by `run_until` when `limit` instructions pass without `check` holding                                                                           |
| `arm6.EmptyRegisterList`   | Raised by `step` on a block transfer with no register listed. Section 7.9 forbids it and does not say what the part does                               |
| `arm6.UnspecifiedEncoding` | Raised by `step` on a word that matches no row of Figure 28                                                                                            |
| `arm6.NoCoprocessor`       | Published and never raised. A coprocessor instruction takes the undefined instruction trap, as section 10.15 says it does with no coprocessor attached |
| `arm6.UnknownMode`         | Raised when the CPSR mode field holds none of the ten modes                                                                                            |
| `arm6.WaitsRequired`       | Raised by `Cycles.ticks(None)`                                                                                                                         |
| `arm6.BadWaits`            | Raised by `Waits` for a figure below 1                                                                                                                 |
| `arm6.ClockClosed`         | Raised by `Clock.tick()` after `close()`                                                                                                               |
| `arm6.Truncated`           | Raised by the decoder when fewer than four bytes are left at the offset. `offset` holds where. `disassemble` ends its listing there instead of raising |
| `arm6.__version__`         | The installed version                                                                                                                                  |

```python
from arm6 import MODELS, Cpu, EmptyRegisterList, Memory, UnknownModelError, UnspecifiedEncoding

for name, model in MODELS.items():
    print(name, model.aliases, Cpu("arm6"), Cpu("ARM60").model.name)

for wrong in ("arm610", ""):
    try:
        Cpu(wrong)
    except UnknownModelError as refused:
        print(str(refused).split(".")[0])


def first_word(word):
    return Cpu("arm60", Memory(image=word.to_bytes(4, "little"), fill=0), fill=0).reset()


for word in (0xE8BD0000, 0xE00000F0):
    try:
        first_word(word).step()
    except (EmptyRegisterList, UnspecifiedEncoding) as refused:
        print(type(refused).__name__, hex(word))

part = first_word(0xEE000000)
part.step()
print(part.mode.name, part.registers.pc)
```

```
arm60 ('arm6',) Cpu('arm60') arm60
'arm610' is not a model this package covers: arm6, arm60
name a model: arm6, arm60
EmptyRegisterList 0xe8bd0000
UnspecifiedEncoding 0xe00000f0
und32 4
```

The name is matched in any case. A block transfer with an empty list and a word Figure 28 has no row for are refused rather than guessed at. A coprocessor instruction enters undefined mode at the vector at address 4.

## Running it at a real speed

`step` reports cycles. It does not say how long they took:

```python
from arm6 import Cpu, Waits

cpu = Cpu("arm60", fill=0).reset()
cpu.step()

print(cpu.spent.ticks(Waits(sequential=1, nonsequential=3, internal=1, coprocessor=1)))
```

```
1
```

Section 8.6 says `mclk` may be stretched without limit and that `Nwait` may insert whole cycles instead. The pin table adds that `Nwait` may be tied HIGH in a system that needs none. How long a cycle takes is therefore a fact about the board. `Waits` describes one: the `mclk` periods each cycle type costs, each at least 1. `Cycles.ticks(waits)` multiplies the four counts by those figures. Asking for ticks without a board is refused:

```python
from arm6 import Cpu, WaitsRequired

cpu = Cpu("arm60", fill=0).reset()
cpu.step()

try:
    cpu.spent.ticks(None)
except WaitsRequired as refused:
    print(str(refused)[:53])
```

```
ARM60 puts memory timing on the Nwait pin and section
```

`Cycles` has `s`, `n`, `i`, `c` and `total`, adds to another `Cycles`, and refuses every attribute write. `total` is also the tick count in the one configuration the pin table names outright: `Nwait` tied HIGH, one `mclk` per cycle.

## Driving it one cycle at a time

`step` runs a whole instruction. `arm6.Clock(cpu)` runs the part on a thread and blocks it at every bus cycle, so a caller can stop between two cycles of one instruction:

```python
from arm6 import Clock, Cpu, Memory

image = (0xEB000000).to_bytes(4, "little") + (0xE1A00001).to_bytes(4, "little") * 8
cpu = Cpu("arm60", Memory(image=image, fill=0), fill=0).reset()

with Clock(cpu) as clock:
    clock.run_for(2)
    print(clock.cycles, cpu.registers.pc, len(cpu.bus.cycles))
```

```
2 8 2
```

The first word is a branch with link to address 8, which costs 3 cycles. After 2 the counter already points at the destination and the third cycle, the second refill fetch, has not happened. `Cpu.run_for` cannot stop there, because it spends whole instructions.

| Clock call                | Effect                                                                                                        | Returns         |
| :------------------------ | :------------------------------------------------------------------------------------------------------------ | :-------------- |
| `tick()`                  | Lets the part run one bus cycle. Raises `ClockClosed` after `close()`, and re-raises anything the part raised | The cycle count |
| `run_for(cycles)`         | `cycles` ticks                                                                                                | The cycle count |
| `close()`                 | Stops the thread and restores the part's `on_cycle`. A `with` block calls it                                  | `None`          |
| Iteration                 | Each step is one `tick()`, until the clock is closed                                                          | The cycle count |
| `cycles`, `closed`, `cpu` | Ticks so far, whether it is closed, the part it drives                                                        |                 |

```python
from arm6 import Clock, ClockClosed, Cpu

cpu = Cpu("arm60", fill=0).reset()
clock = Clock(cpu)

for count in clock:
    if count == 3:
        break

print(clock.tick(), cpu.steps, clock.closed)
clock.close()

try:
    clock.tick()
except ClockClosed as refused:
    print(refused, cpu.on_cycle)
```

```
4 4 False
this clock has been closed None
```

With `fill=0` every word is a 1-cycle `andeq`. Four ticks run four instructions. A tick stops only after everything its cycle does, so the part reads as four `step()` calls leave it, whether the clock is then closed or not.

## Models

```python
from arm6 import MODELS, Cpu

print(sorted(MODELS))
print(Cpu("arm60").model.name, Cpu("arm6").model.name, Cpu("ARM60").model.name)
```

```
['arm60']
arm60 arm60 arm60
```

`arm60` is the name and `arm6` is its alias. The catalogue holds one entry and still refuses a name no model goes by, listing every name it accepts.

The core is the same in ARM60, ARM600 and ARM610. The ARM610 datasheet says the CPU within ARM610 is the ARM6, and gives the ARM600 delta as five bus and packaging differences. The bus differs, and this package models a clocked part down to its bus. Only ARM60 has a document giving its bus cycle by cycle, so only ARM60 is here. ARM600, ARM610 and ARM61 are in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with what each missing document would settle.

## Reading without running

`arm6.disassemble(data, offset=0, address=0, count=None, stop_at_return=False)` reads words instead of executing them. A routine that waits for a status bit and then reads a byte:

```python
from arm6 import disassemble

words = (0xE92D4010, 0xE3A04101, 0xE5D40020, 0xE3100001, 0x0AFFFFFC, 0xE5D40000, 0xE8BD8010)
image = b"".join(word.to_bytes(4, "little") for word in words)

for one in disassemble(image, address=0x100, stop_at_return=True):
    print(f"0x{one.address:06X}  {one.word:08X}  {one.text}")
```

```
0x000100  E92D4010  stmdb SP!, {R4, LR}
0x000104  E3A04101  mov R4, #0x40000000
0x000108  E5D40020  ldrb R0, [R4, #0x20]
0x00010C  E3100001  tst R0, #0x1
0x000110  0AFFFFFC  beq 0x000108
0x000114  E5D40000  ldrb R0, [R4]
0x000118  E8BD8010  ldmia SP!, {R4, PC}
```

Each result is an `arm6.Instruction` with `address`, `offset`, `word`, `condition`, `mnemonic`, `kind`, `operand`, `size` and `text`. `condition` and `kind` use the datasheet's names. `operand` is the one number the operand field denotes, resolved to an address where the addressing is self-contained:

```python
from arm6 import disassemble

image = bytes.fromhex("04 10 9f e5 0e f0 a0 e1 78 56 34 12")

for one in disassemble(image, address=0x8000, count=2):
    print(one.text, "|", one.kind, one.condition, one.mnemonic, one.operand)

print(len(disassemble(b"\x00\x00\xa0\xe1\x00")))
```

```
ldr R1, [PC, #0x4] | single data transfer AL ldr 32780
mov PC, LR | data processing AL mov None
1
```

The load relative to the program counter reports the address its literal sits at, 0x800C, printed as 32780. The `mov` carries no number, so its `operand` is `None`. `count` stops after that many words. A trailing fragment shorter than a word ends the listing.

`disassemble` reads straight through and follows nothing, because whether a word is code depends on how control reached it. This part has no return instruction, only a program counter any instruction may write. `stop_at_return` stops after the two shapes a compiler emits for one, `mov PC, LR` and an `ldm` that loads PC, and after nothing else.

The eleven kinds are Figure 28's rows. That figure has no branch-and-exchange row, no halfword transfer row, no signed load row and no long multiply row. A word matching no row is reported as `unspecified` rather than guessed at.

## Nothing starts clean

```python
from arm6 import Cpu

cpu = Cpu("arm60", seed=7)

print(cpu.registers.read(0) != 0, cpu.registers.pc != 0)
```

```
True True
```

Construction puts every register, the program counter included, in a state derived from `seed`. A part that is stepped before a reset executes from that address, as the silicon would after power comes up.

`reset()` is how a caller gets a known state, and every example above opens with it. It writes only what section 6.3.6 lists: supervisor mode, both interrupt disables, and a fetch from address zero. The saved counter and status it writes are scrambled, because the datasheet says their value is not defined. It costs the two cycles of dummy fetches the datasheet requires plus the three of exception entry, and those five reach `cycles` and `tally`:

```python
from arm6 import Cpu

cpu = Cpu("arm60", fill=0).reset()

print(cpu.registers.pc, cpu.mode.name, cpu.cycles, cpu.steps)
```

```
0 svc32 5 0
```

The counter is at the reset vector, the clock has moved and the instruction count has not. One place in this repository sets the counter by hand instead: the corpus runner, because a recorded case declares the counter, the mode and the interrupt disables, and a reset would destroy the state under comparison.

## Is it right

Three checks hold it, and none of them compares the package with itself.

**The datasheet, quoted and checked.** Every fact in [`conformance/hardware.json`](conformance/hardware.json) carries the sentence it came from and its page. `python3 -m conformance.quotes` places all **62** of them on the page they cite. The ARM60 datasheet has no text layer: `pdftotext` returns eighty three characters for its eighty three pages. So [`conformance/quotes.py`](conformance/quotes.py) renders each cited page with `pdftoppm`, reads it with `tesseract`, and scores a quote by how many of its five-word windows appear on that page.

**A filtered corpus, state only.** `python3 -m conformance.singlestep` runs **424,220** recorded cases from `SingleStepTests/ARM7TDMI`, pinned by commit, and compares the whole processor state after each one. There are **0** disagreements. That corpus was recorded from a later part, so 575,780 of its 1,000,000 ARM-state cases are filtered out. Every exclusion in [`conformance/suites.json`](conformance/suites.json) names the sentence behind it. No cycle, access or transaction-order field is read: ARM60's multiply worst case is `1S+16I` and the ARM7TDMI's is `1S+4I`, so that part's transaction stream describes a different bus.

**The cycle tables.** Every instruction form's cost is held to Table 20 by the tests beside each module. The bus record is compared as well as the total, because a model can spend the right number of cycles driving the wrong addresses.

What is not settled is in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md), and where the documents part ways is in [`conformance/divergences.json`](conformance/divergences.json). The first open question is the ceiling above all of it: nothing here rests on a measurement of real silicon.

| Command                                    | Arguments                                                                                                                                                             | Exit codes                                                                                                                   |
| :----------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------- |
| `python3 arm6/doctor.py`                   | None                                                                                                                                                                  | 0 when every check passes, 1 otherwise                                                                                       |
| `python3 -m conformance.quotes`            | None                                                                                                                                                                  | 0 when every quote that could be read was placed, 1 otherwise. With no document on the machine it checks nothing and says so |
| `python3 -m conformance.singlestep [path]` | The corpus `v1` directory, `external/ARM7TDMI/v1` by default. `--limit N` cases per file, `--count` to count without comparing, `--files` to print the paths to fetch | 0 with no disagreement or no corpus, 1 on any disagreement                                                                   |
| `python3 -m conformance.speed`             | `--cycles N`, 200,000 by default, and `--repeats N`, 7 by default                                                                                                     | 0 above the floor, 1 below it, 2 on a bad option                                                                             |
| `python3 -m conformance.documents`         | `--check` to verify without fetching, `--only SUBSTRING` to pick documents                                                                                            | 0 when every document verifies, 1 otherwise                                                                                  |
| `python3 -m conformance.links`             | None. It probes every address in this README                                                                                                                          | 0 unless an address answers 404 or 410                                                                                       |
| `python3 -m conformance.package <wheel>`   | A built wheel                                                                                                                                                         | 0 when every module is shipped and no test is, 1 otherwise, 2 with no argument                                               |

## Working on it

| Need                                                            | Where                                                           |
| :-------------------------------------------------------------- | :-------------------------------------------------------------- |
| Every gate and the order to run them                            | [CONTRIBUTING.md](CONTRIBUTING.md)                              |
| The same material for a coding agent                            | [AGENTS.md](AGENTS.md)                                          |
| The standard this repository shares with the rest of the family | [FAMILY.md](FAMILY.md)                                          |
| Bug reports                                                     | [GitHub Issues](https://github.com/gufranco/arm6-python/issues) |
| Security reports                                                | [SECURITY.md](SECURITY.md)                                      |

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx mypy@1.14.1
python3 arm6/core.test.py
```

Each module has a test file beside it, named after it, and each runs on its own as above. Coverage is a hard gate at 100% statement and branch. `python3 -m conformance.speed` is the throughput floor and runs outside the coverage step, because a coverage tracer costs about ten times what the model does.

## References

None of these documents is redistributable, and none is in this repository. Individual sentences are quoted in [`conformance/hardware.json`](conformance/hardware.json) with the page they are printed on. Each row gives the page count and the first sixteen hex digits of the file's SHA-256.

| Document                                                                                                                                                            | Date    | Pages | SHA-256            |
| :------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------ | ----: | :----------------- |
| [GEC Plessey Semiconductors, _ARM60 Datasheet_, Issue 0.81](https://3dodev.com/_media/documentation/hardware/arm60_datasheet_-_gec_plessey_semiconductors.pdf)      | 1993    |    83 | `315dbff7b6259a73` |
| [Advanced RISC Machines, _ARM610 Data Sheet_, ARM DDI 0004D](https://bitsavers.org/pdf/acorn/ARM_DDI_0004D_ARM610_Data_Sheet_Aug93.pdf)                             | 1993-08 |   134 | `76f13ffe2bc20774` |
| [Advanced RISC Machines, _Application Note 11: Differences Between ARM6 and Earlier ARM Processors_](https://home.marutan.net/rpcemu/Apps11vC.html)                 | Undated |     1 | `41239bc21c8e3375` |
| [ARM Limited, _ARM Architecture Reference Manual_, ARM DDI 0100E](https://www.cl.cam.ac.uk/teaching/0405/ECADArch/datasheets/arm.pdf)                               | 2000    |   811 | `fa405a69d371c533` |
| [VLSI Technology, _Acorn RISC Machine (ARM) Family Data Manual_](https://bitsavers.mirrorservice.org/components/vti/1990_Acorn_RISC_Machine_Family_Data_Manual.pdf) | 1990    |   322 | `f3a524aeec44ab45` |

[`conformance/documents.json`](conformance/documents.json) carries the full digest, the byte count and a fetchable address for each. `python3 -m conformance.documents` downloads all five into `docs/`, which git ignores, and refuses any file whose digest differs. `--check` verifies the copies already there. The manifest fetches the ARM610 data sheet from a mirror, because the address linked above answers a plain fetch with 403. Both serve the same bytes.

The ARM60 datasheet decides. It is the only document found that gives this part's bus per instruction and per cycle. The ARM610 data sheet is a second witness for the instruction set and the programmer's model, and for nothing else: its bus chapter describes two clocks, two cycle types and a cache. Application Note 11 is the only document found that prints the four 26-bit mode encodings, which both datasheets leave out. ARM DDI 0100E states the shifter carry after an immediate rotate, which the ARM60 datasheet leaves out. The VLSI data manual was read for the ARM2aS macrocell and documents other parts, so it settles nothing here.

[SingleStepTests/ARM7TDMI](https://github.com/SingleStepTests/ARM7TDMI) supplies the recorded cases. Its commit and every filter entry are in [`conformance/suites.json`](conformance/suites.json).

## Citing this

[CITATION.cff](CITATION.cff) is updated with each release by the script that stamps the package version.

## License

MIT. See [LICENSE](LICENSE).

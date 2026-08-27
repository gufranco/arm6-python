# ARM6

An ARM60 you can drive from a clock, held to its own datasheet for every instruction and every cycle it spends, and to a filtered corpus for the whole processor state after each one.

[![CI](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/arm6-python/actions/workflows/ci.yml)

**1** part, **62** quoted sentences placed on the page they cite, **424,220** recorded cases compared, **0** disagreements, **905** tests, **100%** statement and branch coverage, no dependencies

```python
from arm6 import Cpu, Memory

cpu = Cpu("arm60", Memory(image=(0xE3A0002A).to_bytes(4, "little"), fill=0)).reset()

spent = cpu.step()

print(f"{cpu.registers.read(0):#010x} in {spent} cycle, {cpu.spent}")
```

```
0x0000002a in 1 cycle, Cycles(s=1, n=0, i=0, c=0)
```

One instruction, loading `42` into the first register. It cost one sequential cycle, which is what Table 20 says a data operation costs.

## Install

```bash
pip install git+https://github.com/gufranco/arm6-python.git
```

Python 3.12 or newer. Nothing else.

## The interface

Everything a caller touches. Nothing else is public.

| Call | Does | Returns |
|:--|:--|:--|
| `Cpu(model, memory=None)` | Builds the part. The model is required and there is no default | `Cpu` |
| `reset()` | Section 6.3.6, including the cycles it costs | the part, so the call chains |
| `step()` | One instruction | the cycles it cost |
| `run_for(cycles)` | A budget, which an instruction may overshoot | what was really spent |
| `run_until(check, limit)` | Steps while `check(cpu)` is false | the part; `RunLimit` if the limit is hit |
| `held()` | Whether the part has stopped advancing the program | `False`, always, and the reason is below |
| `irq()`, `fiq()` | Offer a line and say whether it would be taken | `bool` |
| `cycles`, `steps` | Cycles since construction, instructions since the last reset | `int` |
| `spent`, `tally` | The last instruction's cost and the running total, in S, N, I and C | `Cycles` |
| `bus.cycles` | What the last instruction drove on the pins, row by row | `list[Cycle]` |

## Running it at a real speed

This is the one place this member behaves differently from its siblings, and the difference is the datasheet's rather than a preference.

`step` reports cycles. It will not tell you how long they took:

```python
from arm6 import Cpu, Waits

cpu = Cpu("arm60", fill=0).reset()
cpu.step()

print(cpu.spent.ticks(Waits(sequential=1, nonsequential=3, internal=1, coprocessor=1)))
```

```
1
```

Section 8.6 says `mclk` may be stretched without limit and that `Nwait` may insert whole cycles instead, and the pin table adds that `Nwait` may be tied HIGH in a system that needs none. So how long a cycle takes is a fact about the board. Asking for ticks without describing one is refused rather than answered:

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

The integer `step` returns is the cycle count, which is also the tick count in the one configuration the pin table names outright: `Nwait` tied HIGH, one `mclk` per cycle.

## Driving it one cycle at a time

`step` runs a whole instruction because that is the unit a program is written in. A board has no such unit, so `Clock` runs the part on a thread and lets it block where the cycle is spent:

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

Two cycles into a three-cycle branch with link: the counter has been redirected and the third cycle, which refills the pipeline from the destination, has not happened. The part's own `run_for` cannot stop there, because an instruction is not divisible and it would have spent all three.

## Models

One part, and a catalogue anyway:

```python
from arm6 import MODELS, Cpu

print(sorted(MODELS))
print(Cpu("arm60").model.name, Cpu("arm6").model.name, Cpu("ARM60").model.name)
```

```
['arm60']
arm60 arm60 arm60
```

`arm60` is the name and `arm6` is the alias it answers to. A name no model goes by is refused with every model there is listed, which is what a catalogue buys even when it holds one entry.

The core is the same in ARM60, ARM600 and ARM610: the ARM610 datasheet says outright that the CPU within ARM610 is the ARM6, and gives the ARM600 delta as five bus and packaging differences. The bus is not the same, and the bus is what this family models a clocked part down to. Only ARM60 has a document giving it cycle by cycle, so only ARM60 is here. The other three are in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with what each of their documents would settle.

## Reading without running

A word can be read rather than executed:

```python
from arm6 import decode

print(decode.describe(0x0AFFFFFE))
print(decode.describe(0xE0010293))
```

```
EQ branch
AL multiply
```

The eleven rows are Figure 28's, and what that figure does not have decides as much as what it does: no branch-and-exchange row, no halfword transfer row, no signed load row and no long multiply row. An encoding matching none of them is reported as outside the figure rather than guessed at.

## Nothing starts clean

```python
from arm6 import Cpu

cpu = Cpu("arm60", seed=7)

print(cpu.registers.read(0) != 0, cpu.registers.pc != 0)
```

```
True True
```

Construction puts every register in the state the rail coming up leaves it, the program counter included, so a newly built part executes rubbish from a rubbish address exactly as the silicon would. Nothing arrives reset and nothing arrives cleared, because no board offers either.

`reset()` is therefore how a caller gets anywhere, and it is what every example above opens with. It writes only the three things section 6.3.6 lists, forcing supervisor mode, setting both interrupt disables and fetching from address zero, and the saved counter and status it writes are scrambled because the datasheet says their value is not defined. It is not free either: it costs the two cycles of dummy fetches the datasheet requires plus the three of exception entry, and those five appear in the tally like any others.

```python
from arm6 import Cpu

cpu = Cpu("arm60", fill=0).reset()

print(cpu.registers.pc, cpu.mode.name, cpu.cycles, cpu.steps)
```

```
0 svc32 5 0
```

The counter is at the reset vector, the clock has moved and the instruction count has not. One place in this repository sets the counter by hand instead: the corpus runner, because a recorded case declares the counter, the mode and the interrupt disables, and resetting would destroy the state under comparison.

`fill=0` is how a caller asks for something quieter, and it exists for runs that have to get through a few dozen instructions rather than for convenience.

## Is it right

Three things hold it, and none of them is this package agreeing with itself.

**The datasheet, quoted and checked.** Every fact in [`conformance/hardware.json`](conformance/hardware.json) carries the sentence it came from and the page it was on, and `conformance/quotes.py` places all **62** of them on the page they cite. That check is harder here than in the sibling repositories and it matters more: the ARM60 datasheet carries no text layer at all, so `pdftotext` returns one newline per page and a search of it would find nothing while meaning nothing. Each page is rendered and recognised instead.

**A filtered corpus, state only.** `conformance/singlestep.py` runs **424,220** recorded cases from `SingleStepTests/ARM7TDMI`, pinned by commit, and compares the whole processor state after each one. There are **0** disagreements. That corpus was recorded from a later part, so 575,780 of its million ARM-state cases are filtered out and every exclusion in [`conformance/suites.json`](conformance/suites.json) names the sentence behind it. No cycle, access or transaction-order field is ever read: ARM60's multiply worst case is `1S+16I` and the ARM7TDMI's is `1S+4I`, so that part's transaction stream is a different bus.

**The cycle tables.** Every instruction form's cost is held to Table 20, and the bus record is compared as well as the total, because a model can spend the right number of cycles driving the wrong addresses.

What is not settled is in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md), including the ceiling above all of it: nothing here rests on a measurement of real silicon.

## Working on it

```bash
ruff format --check . && ruff check .
mypy
pnpm run format:check
python3 -m coverage erase
for file in $(find arm6 conformance -name '*.test.py' | sort); do
  python3 -m coverage run -a "$file"
done
python3 -m coverage report
```

Then the checks that read something this repository does not carry, each of which reports what it could not do rather than passing quietly:

```bash
python3 -m conformance.quotes
python3 -m conformance.singlestep path/to/ARM7TDMI/v1
python3 -m conformance.speed
python3 arm6/doctor.py
```

`conformance/quotes.py` needs `pdftoppm` and `tesseract` on the machine, because of the missing text layer. The doctor says whether they are there.

## References

This repository carries no documents. Every claim is traced to something published elsewhere, listed here so a reader can fetch the same file and check the same page. Each row gives the page count and the first sixteen characters of the file's SHA-256, because links move and a link that has rotted into a different scan is easy to follow without noticing. Compute the full digest with `shasum -a 256 <file>`.

Every document below is copyrighted and not redistributable, which is why none is in this repository. Individual sentences are quoted in [`conformance/hardware.json`](conformance/hardware.json) with the page they are printed on.

| Document | Date | Pages | SHA-256 | Redistributable |
|:--|:--|--:|:--|:--|
| [GEC Plessey Semiconductors, *ARM60 Datasheet*, Issue 0.81](https://3dodev.com/_media/documentation/hardware/arm60_datasheet_-_gec_plessey_semiconductors.pdf) | 1993 | 83 | `315dbff7b6259a73…` | No |
| [Advanced RISC Machines, *ARM610 Data Sheet*, ARM DDI 0004D](https://bitsavers.org/pdf/acorn/ARM_DDI_0004D_ARM610_Data_Sheet_Aug93.pdf) | 1993-08 | 134 | `76f13ffe2bc20774…` | No |
| [Advanced RISC Machines, *Application Note 11: Differences Between ARM6 and Earlier ARM Processors*](https://home.marutan.net/rpcemu/Apps11vC.html) | undated | 1 | `41239bc21c8e3375…` | No |

The first of the three is the one that decides. It is the only document found that gives this part per instruction and per cycle, and it is the only one here with no text layer at all: `pdftotext` returns eighty three characters for its eighty three pages. Every page a quotation cites is therefore rendered and read rather than searched, and the checker that does it is [`conformance/quotes.py`](conformance/quotes.py).

The ARM610 datasheet is a second witness for the instruction set and the programmer's model, and for nothing else: its bus chapter describes two clocks, two cycle types and a cache, none of which the ARM60 has. Application Note 11 is the only document found that prints the four 26-bit mode encodings, which both datasheets leave out.

| Source | Used for |
|:--|:--|
| [SingleStepTests/ARM7TDMI](https://github.com/SingleStepTests/ARM7TDMI) | The recorded cases the core is compared against, state only. Commit and filter in [`conformance/suites.json`](conformance/suites.json) |

The family standard every repository here is built to is in [FAMILY.md](FAMILY.md).

## Citing this

See [CITATION.cff](CITATION.cff).

## License

MIT. See [LICENSE](LICENSE).

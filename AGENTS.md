# Working in this repository

Read [FAMILY.md](FAMILY.md) first. It is the standard every member of this
family carries, byte for byte, and it decides most questions before they are
asked. What follows is only what is true of this member. [README.md](README.md)
is the document written for a person.

## What this project is, in one paragraph

The ARM60: a 32 bit RISC processor with a 32 bit address bus, modelled from ARM's
own documents and driven a cycle at a time. The core is the same in ARM60, ARM600
and ARM610, and the bus is not, so the catalogue holds the one part a bus document
was found for. What makes this member different from its siblings is that it will
not tell you how long anything took: ARM60 puts memory timing on the `Nwait` pin
and states that the clock may be stretched without limit, so the duration of a
cycle is a fact about the board rather than about the part. `step` reports cycles,
`spent` holds them in the manufacturer's own S, N, I and C terms, and `ticks`
converts once a caller has described their own memory system.

## The interface a caller drives

The family's clocked shape, unchanged, plus one addition and one refusal.

| Call                                 | What it does                                                           |
| :----------------------------------- | :--------------------------------------------------------------------- |
| `Cpu(model, memory)`                 | Builds the part. The model is required and there is no default         |
| `step()`, `run_for()`, `run_until()` | The family's three ways to drive it                                    |
| `reset()`                            | Section 6.3.6, including the cycles it costs, handed back for chaining |
| `held()`                             | Always false, because nothing stops this part advancing                |
| `irq()`, `fiq()`                     | The two lines, both maskable, FIQ the higher priority                  |
| `spent`, `tally`                     | The cost of the last instruction and the running total, as `Cycles`    |
| `spent.ticks(waits)`                 | A duration, once a caller says what their board costs. Refuses without |
| `bus.cycles`                         | What the last instruction drove on the pins, one row per table row     |

## The authority ladder

1. **The ARM60 datasheet**, for anything it prints: the instruction set, the
   programmer's model, the memory interface, and chapter 10's per-instruction
   per-cycle bus behaviour.
2. **ARM DDI 0004D**, the ARM610 datasheet, as a second witness for the
   instruction set and the programmer's model, never for a timing.
3. **ARM Application Note 11**, for the four 26-bit mode encodings no datasheet
   tabulates, and for the rule saying what an unobserved restriction does.
4. **ARM DDI 0100E**, the Architecture Reference Manual, for instruction-level
   behaviour the datasheets leave unstated and it states for architecture
   version 3, never for a timing.
5. **The filtered ARM7TDMI corpus**, state only, for behaviour no document
   specifies.

A rung above beats a rung below. Rungs two and three of the _family's_ ladder, a
measurement on real hardware and a simulation of the die, are both empty here and
the record says so.

`ARM DDI 0020C` and `ARM DDI 0024C` are deliberately absent. They are ARMv3 and
they disagree with ARM6 in three rows of the speed table, so they are witnesses
that the timings differ rather than witnesses to what they are.

## What is settled and what is not

**Not settled: 9 things**, each in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with
the measurement that would close it. Four more are deliberately not modelled and
are listed separately, so an omission reads as a decision rather than an oversight.

Settled: every instruction's behaviour and every instruction's cost, both from the
datasheet, with 424,220 recorded cases agreeing on the processor state after each
one.

## The document has no text layer, and that changes the checking

This is the thing most likely to waste a session here.

Asking `pdftotext` for the ARM60 datasheet's contents returns one newline per
page: eighty three characters for eighty three pages. Every other member of this
family reads its documents that way, so the sibling quote checker ported unchanged
would find nothing, report nothing missing, and exit zero over a document it had
not read.

So `conformance/quotes.py` renders each cited page with `pdftoppm` and reads it
with `tesseract`, caching the result beside the document. Both tools have to be on
the machine and the doctor says whether they are. A quote is scored on how many of
its five-word windows appear on the page it cites, which survives a misread word
and still fails a sentence that was never printed.

Two failures were driven through it deliberately: a sentence nobody printed, and a
real sentence filed under the wrong page. Both are reported.

## Adding a part to the family

`MODELS` holds one entry and publishes a catalogue anyway. Adding ARM600, ARM610
or ARM61 needs a document giving that part's bus at the resolution of ARM60's
chapter 10, and no such document has been found for any of them. The instruction
set would carry across unchanged; the bus would not.

## Test cartridges

[`conformance/testroms.json`](conformance/testroms.json) lists one image, keyed
by its SHA-256 and never committed: the coprocessor program dump in
`snes-roms/5 Tools & Service Test Carts/CPU/` in the local library. Nothing
here runs it and nothing here reads it, so there is no runner and no command.
The program finds its program, data, work memory and command ports through
the coprocessor's memory map, which this member does not model, and it reports
no verdict of its own. It is `hosted` and waits on `snes-st-python`, the member
that builds that map around this core.

The ARM7TDMI corpus pinned in
[`conformance/suites.json`](conformance/suites.json) is a recorded state corpus
rather than an image, so it is not listed there, and it remains the external
check on this core's behaviour.

## Every gate, in the order to run them

```bash
uvx ruff@0.16.3 format --check .
uvx ruff@0.16.3 check .
uvx --python 3.12 --with types-setuptools==84.0.0.20260812 mypy==1.14.1
pnpm run format:check
uvx yamllint==1.38.0 --strict .
cov=(uvx --python 3.12 --from coverage==7.6.10 --with setuptools==84.0.0 coverage)
"${cov[@]}" erase
for file in $(find arm6 conformance -name '*.test.py' | sort); do
  "${cov[@]}" run -a "$file"
done
"${cov[@]}" report
```

Then the throughput floor, which runs outside the coverage step because a tracer
costs about ten times what the model does:

```bash
python3 -m conformance.speed
```

And the runs that report what they could not check rather than passing quietly:

```bash
python3 -m conformance.quotes
python3 -m conformance.singlestep path/to/ARM7TDMI/v1
python3 arm6/doctor.py
```

Everything under `conformance/` runs as a module. Run as a script, its own
directory goes on the import path and a file there shadows any standard library
module of the same name. `doctor.py` is the exception and runs as a file on
purpose, so that it still runs when the package itself will not import, which is
the case it exists for.

## Conventions that are not negotiable

- Python only, standard library only, no dependencies.
- No comments in source, and a docstring counts as one. A step that would need
  a comment is a step that should be a named function.
- Tests sit beside the module they cover as `<module>.test.py`. Arrange, act
  and assert, each block opened by its bare marker.
- 100% statement and branch coverage, enforced. `mypy` at strict, with every
  optional error class on.
- Everything a caller can catch is defined once, in `arm6/errors.py`, and
  imported from there.
- A check nobody has seen fail is not known to work. Drive every new check
  against input that should fail it before keeping it.

The linter's ignores in [`pyproject.toml`](pyproject.toml) carry no comments, so
their reasons live here:

- `N818`: some exceptions are control flow signals rather than failures. The
  standard library names those without the suffix too, and the ones that report
  a failure do end in `Error`.
- `N999` in tests: a test file sits beside its module and is named after it with
  a dot, so a module and its tests are read together.
- `T201` in `conformance/`: these are command line tools, and printing is their
  output.
- `BLE001` and `T201` in `environment.py`: a check that throws has to become a
  line in the report rather than end the run, and the report is the product.
- `BLE001` and `T201` in the doctor: it has to survive whatever a check throws
  and report it. A narrower catch would let a traceback take the rest of the
  report with it.

The coverage exclusions carry none either:

- `if __name__ == "__main__":`: the guard hands argv to a function that is
  itself tested, and importing the module to cover it would run the tool.
- `if TYPE_CHECKING:`: the block never runs. Python 3.14 drops it before
  coverage sees it and earlier versions do not, so counting it would make the
  gate mean something different on each runtime.
- `^\s*\.\.\.$` and `: \.\.\.$`: a protocol method's ellipsis is a contract the
  type checker reads and the runtime never runs.
- `@unittest\.skipUnless\(A_PART,`,
  `@unittest\.skipUnless\(A_PART and BUILDABLE,` and
  `^def accounts_for_a_reset\(` in the coverage exclusions: this member is not a
  part, so the family tests that build a `Chip` and account for its reset are
  skipped here and their bodies never run.

The formatter's ignores in [`.prettierignore`](.prettierignore) carry no
comments either, so their reasons live here:

- `pnpm-lock.yaml` and `package-lock.json`: the package manager writes them, in
  its own layout, on every install.
- `node_modules/`, `.venv/`, `venv/`, `build/`, `dist/` and `*.egg-info/`:
  installed or built, never written by hand.
- `.coverage`, `coverage.json`, `htmlcov/` and the tool caches: the output of a
  run, never committed.
- `docs/`, `specs/`, `.work/` and `.claude/`: local working material, never
  committed.

## Layout

```text
arm6/
  __init__.py     the package, and the part chosen at construction
  models.py       the catalogue, and why it holds one entry
  core.py         the part: reset, step, the exception vectors, the two lines
  dataops.py      the data processing row, the multiply row, the PSR transfers
  transfers.py    branches, loads, stores, swaps and traps
  decode.py       which of Figure 28's eleven rows a word is, or that it is none
  shifter.py      the barrel shifter, including every corner spelled out separately
  registers.py    thirty seven registers and the banks a mode cannot see
  psr.py          the status register, ten modes, and bit 5 reserved
  memory.py       four gigabytes of it, sparse, and none of it clean
  bus.py          one row of a chapter 10 table, with the pipelining kept
  tally.py        S, N, I and C, and the refusal to turn them into a duration
  clock.py        the part advanced a cycle at a time rather than an instruction
  errors.py       everything this package raises, in one place
  doctor.py       what is actually on this machine, printed for a bug report
  version.py      rewritten by the release job and by nothing else
conformance/
  family_*.test.py the family standard, held to this repository, one topic a file
  family_member.py what this member answers to them
  family_shared.py what more than one of them reads
  hardware.json   every fact, with the sentence it came from and its page
  hardware.test.py the facts no test beside a module already held
  printed.py      reads a fact out of hardware.json by its key, for the tests that hold it
  divergences.json where sources part, and what would settle each
  suites.json     the corpus pin, and every filter entry with its sentence
  quotes.py       every quoted sentence, against the page it cites
  singlestep.py   the filtered corpus, state only
  speed.py        the throughput floor
  links.py        the weekly check that every cited address still answers
  documents.json  every document by digest, byte count and fetchable address
  documents.py    brings them down into docs/, and refuses anything that differs
```

## Things that will bite you

- **`step` returns an integer and the breakdown is on the part.** CPython refuses
  a non-empty `__slots__` on a subclass of `int`, and the family requires every
  published class to declare its slots, so the count and the four-way breakdown
  cannot live on one object. `step` hands back the count and `cpu.spent` holds the
  breakdown of the instruction that produced it.
- **Words 0 to 15 of a corpus state block are the base bank, not the current
  mode's view.** A branch with link executed in IRQ mode leaves the link in word
  28 and word 14 keeps what it held. Reading word 14 as the visible R14 makes
  every such case look like a model defect.
- **`pdftoppm` zero-pads the page number to the width of the page count.** Page 4
  of an eighty three page document lands in `page-04.png`, so a reader looking for
  `page-4.png` finds nothing, the page reads as empty, and every quotation cited
  to it is reported as unchecked rather than as missing. `-singlefile` avoids the
  whole question and is not a tidiness choice.
- **Table 5 and Table 20 disagree about one cycle** of a register-specified shift,
  and the model follows Table 5. The reasoning is in
  [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md); do not quietly switch it.
- **The reserved bits of a PSR are written rather than masked.** Section 7.4.2
  does say they shall be preserved, under a heading introducing rules a _program_
  should observe. Masking them in the model would be inventing a gate the document
  never describes, and the read-modify-write advice only makes sense if the
  silicon writes what it is given.
- **The corpus filter is read out of the document, not out of the failures.**
  Nearly every entry is a sentence of the form "shall not be used", collected by
  reading for that phrase. Adding an entry because a comparison failed is the same
  work in the opposite order and a very different thing.

## Before calling anything finished

Every gate above, green, with output shown. A claim without a run behind it is
not evidence. If a check was skipped because a file is not on this machine, say
which check and why rather than reporting a pass.

## What a change is expected to leave behind

A test that fails without the change and passes with it. An entry in
[OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) if it turned a settled thing into an open
one, or removed one. Nothing in `docs/` under version control, ever.

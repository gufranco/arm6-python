## What this changes

One or two sentences. What is different afterwards, and why it needed to be.

## How it was checked

Paste the output rather than describing it. A claim that the tests pass is not
evidence that they did.

```text
```

- [ ] `ruff format --check .` and `ruff check .` are clean
- [ ] Every test file runs, and coverage is 100% of statements and branches
- [ ] `python3 -m upd7725.doctor` reports nothing on this machine
- [ ] The instruction sweep in `conformance/` still reports zero disagreements

## If this changes what an instruction does

Say which encoding, which processor, and what the new behaviour was measured
against. Everything here is held to an independent implementation, so a change
that is not measured against one is a change nobody can check.

## What it does not carry

- [ ] No microcode, and no bytes from any
- [ ] Nothing that says where to obtain it

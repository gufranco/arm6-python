"""Which parts this package covers, and why that is one part today.

The core is the same across ARM60, ARM600 and ARM610. The ARM610 datasheet says
so outright, and gives the ARM600 delta as five items every one of which is a bus
or a packaging difference rather than a core one. So the instruction set carries
across all three.

The bus does not, and the bus is what this family models a clocked part down to.
ARM610's bus chapter describes a different machine from ARM60's: two clocks
rather than one, two cycle types rather than four, `SEQ` derived from `nMREQ`
rather than driven independently, the clock a cycle runs on decided by whether
the cache hit, and sequential runs broken at 256-word boundaries so the memory
management unit can check the next sub-page. No document gives ARM600 or ARM610
at the resolution chapter 10 gives ARM60.

So the catalogue holds ARM60, and ARM600, ARM610 and ARM61 are recorded in
OPEN-QUESTIONS.md as parts whose documents have not been found, each naming what
its would settle. ARM61 is a real part rather than a guess: the ARM60 datasheet
names it twice, in the endianness list and in the early-abort list.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import override

from arm6.errors import UnknownModelError


class Model:
    """One part, and the names a caller may reach it by."""

    __slots__ = ("aliases", "name", "summary")

    name: str
    summary: str
    aliases: tuple[str, ...]

    def __init__(self, name: str, summary: str, aliases: Iterable[str] = ()) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "aliases", tuple(aliases))

    @override
    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("a model is a catalogue entry and does not change")

    @override
    def __repr__(self) -> str:
        return f"Model({self.name!r})"


MODELS: dict[str, Model] = {
    "arm60": Model(
        "arm60",
        "The ARM60: a 32 bit RISC processor with a 32 bit address bus, "
        "held to its own datasheet for every instruction and every cycle",
        aliases=("arm6",),
    ),
}

_BY_ALIAS = {alias: model for model in MODELS.values() for alias in (model.name, *model.aliases)}


def resolve(name: object) -> Model:
    """The part a name refers to, refusing anything else.

    Refusing costs a file and buys two things: the same call everywhere in the
    family, and a typo that is reported rather than quietly building the only
    part there is. A constructor that accepts any string and returns its single
    entry is a constructor that cannot report a mistake.
    """
    if not isinstance(name, str) or not name:
        raise UnknownModelError(
            f"name a model: {', '.join(sorted(_BY_ALIAS))}. "
            "There is no default, because a caller who learns to leave it out here "
            "writes the same call against a member covering sixteen parts."
        )
    found = _BY_ALIAS.get(name.lower())
    if found is None:
        raise UnknownModelError(
            f"{name!r} is not a model this package covers: {', '.join(sorted(_BY_ALIAS))}"
        )
    return found

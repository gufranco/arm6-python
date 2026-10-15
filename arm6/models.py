from __future__ import annotations

from collections.abc import Iterable
from typing import override

from arm6.errors import UnknownModelError


class Model:
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

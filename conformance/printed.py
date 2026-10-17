from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

RECORD = Path(__file__).resolve().parent / "hardware.json"


@cache
def facts() -> dict[str, dict[str, Any]]:
    held: dict[str, Any] = json.loads(RECORD.read_text())
    return {name: fact for part in held["parts"] for name, fact in part["facts"].items()}


def value(name: str) -> Any:
    return facts()[name]["value"]


def quote(name: str) -> str:
    return str(facts()[name]["quote"])

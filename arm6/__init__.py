"""The ARM6: a 32 bit RISC processor, held to its own datasheet cycle by cycle.

    from arm6 import Cpu

    cpu = Cpu("arm60").reset()
    cpu.step()
    cpu.spent.ticks(waits)

One instruction set across ARM60, ARM600 and ARM610, and one bus that is only
documented for the first of them. The catalogue holds ARM60 because ARM60 is the
part a datasheet was found for; the other three are recorded as open questions
naming what each of their documents would settle.

What separates this package from the other clocked members of the family is that
it will not tell you how long anything took. ARM60 puts memory timing on the
`Nwait` pin and states that the clock may be stretched without limit, so the
duration of a cycle is a fact about the board. `step` reports cycles, `spent`
holds them in the manufacturer's own S, N, I and C terms, and `ticks` converts
once a caller has said what their memory system costs.
"""

from __future__ import annotations

from . import bus as bus
from . import clock as clock
from . import core as core
from . import dataops as dataops
from . import decode as decode
from . import disassembly as disassembly
from . import errors as errors
from . import memory as memory
from . import models as models
from . import psr as psr
from . import registers as registers
from . import shifter as shifter
from . import tally as tally
from . import transfers as transfers
from .clock import Clock
from .core import VECTORS, Cpu
from .disassembly import Instruction, disassemble
from .errors import (
    Arm6Error,
    BadWaits,
    ClockClosed,
    RunLimit,
    Truncated,
    UnknownModelError,
    WaitsRequired,
)
from .memory import UNSET_SEED, Memory
from .models import MODELS, Model
from .psr import MODES, Mode, UnknownMode
from .registers import Registers
from .tally import Cycles, Waits
from .transfers import EmptyRegisterList, NoCoprocessor, UnspecifiedEncoding
from .version import VERSION

__version__ = VERSION

__all__ = [
    "MODELS",
    "MODES",
    "UNSET_SEED",
    "VECTORS",
    "Arm6Error",
    "BadWaits",
    "Clock",
    "ClockClosed",
    "Cpu",
    "Cycles",
    "EmptyRegisterList",
    "Instruction",
    "Memory",
    "Mode",
    "Model",
    "NoCoprocessor",
    "Registers",
    "RunLimit",
    "Truncated",
    "UnknownMode",
    "UnknownModelError",
    "UnspecifiedEncoding",
    "Waits",
    "WaitsRequired",
    "__version__",
    "disassemble",
]

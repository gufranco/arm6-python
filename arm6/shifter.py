"""The barrel shifter, including every corner the datasheet spells out separately.

Two forms exist and they are not the same function with a different argument.
When the amount comes from the instruction it is five bits, and the four
encodings that would read as zero are reused: `LSL #0` passes the old carry
through, `LSR #0` means `LSR #32`, `ASR #0` means `ASR #32`, and `ROR #0` is
rotate right extended, a rotate of the thirty three bit quantity made by putting
the C flag above Rm. When the amount comes from a register it is a whole byte,
zero means zero, and section 7.3.2 enumerates seven separate outcomes for
thirty two and above.

Keeping the two forms as two functions is deliberate. Collapsing them costs the
distinction between `ROR #0`, which is RRX, and a rotate by a register holding
zero, which is not.
"""

from __future__ import annotations

WORD_MASK = 0xFFFFFFFF

SIGN_BIT = 31

LSL = 0
LSR = 1
ASR = 2
ROR = 3

CODES = (LSL, LSR, ASR, ROR)
"""The two bit shift field, in the order the encoding numbers it."""


def _check(code: int) -> None:
    if code not in CODES:
        raise ValueError(f"shift code {code} is not one of the two bit field's four values")


def _bit(value: int, place: int) -> bool:
    return bool(value >> place & 1)


def _asr(value: int, amount: int) -> int:
    """Shift right filling the top with bit 31, which is what preserves the sign."""
    if _bit(value, SIGN_BIT):
        return (value >> amount | ~0 << (32 - amount)) & WORD_MASK
    return value >> amount


def _ror(value: int, amount: int) -> int:
    return (value >> amount | value << (32 - amount)) & WORD_MASK


def _between_one_and_thirty_one(code: int, value: int, amount: int) -> tuple[int, bool]:
    """The general rule, for the amounts where there is one.

    Both forms agree here, which section 7.3.2 states outright: an amount between
    one and thirty one from a register matches an instruction-specified shift of
    the same value exactly.
    """
    if code == LSL:
        return (value << amount) & WORD_MASK, _bit(value, 32 - amount)
    if code == LSR:
        return value >> amount, _bit(value, amount - 1)
    if code == ASR:
        return _asr(value, amount), _bit(value, amount - 1)
    return _ror(value, amount), _bit(value, amount - 1)


def by_amount(code: int, value: int, amount: int, carry: bool) -> tuple[int, bool]:
    """A shift whose amount came from the five bit field in the instruction.

    The four zero encodings are the point of this function. Three of them mean
    something other than a shift of nothing, and the fourth, `LSL #0`, is the one
    case where the shifter's carry output is the flag that was already there
    rather than a bit of Rm.
    """
    _check(code)
    value &= WORD_MASK
    if amount != 0:
        return _between_one_and_thirty_one(code, value, amount)
    if code == LSL:
        return value, carry
    if code == LSR:
        return 0, _bit(value, SIGN_BIT)
    if code == ASR:
        return (WORD_MASK if _bit(value, SIGN_BIT) else 0), _bit(value, SIGN_BIT)
    return (int(carry) << SIGN_BIT | value >> 1) & WORD_MASK, _bit(value, 0)


def by_register(code: int, value: int, amount: int, carry: bool) -> tuple[int, bool]:
    """A shift whose amount came from the bottom byte of a register.

    Only the least significant byte of Rs decides the amount. A byte of zero
    leaves Rm alone and passes the old carry on, which is the same outcome as
    `LSL #0` and reached for a different reason: here nothing was shifted, there
    the encoding was reused.
    """
    _check(code)
    value &= WORD_MASK
    amount &= 0xFF
    if amount == 0:
        return value, carry
    if amount < 32:
        return _between_one_and_thirty_one(code, value, amount)
    if code == LSL:
        return 0, (_bit(value, 0) if amount == 32 else False)
    if code == LSR:
        return 0, (_bit(value, SIGN_BIT) if amount == 32 else False)
    if code == ASR:
        return (WORD_MASK if _bit(value, SIGN_BIT) else 0), _bit(value, SIGN_BIT)
    folded = amount % 32
    if folded == 0:
        return value, _bit(value, SIGN_BIT)
    return _between_one_and_thirty_one(ROR, value, folded)

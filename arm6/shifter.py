from __future__ import annotations

WORD_MASK = 0xFFFFFFFF

SIGN_BIT = 31

LSL = 0
LSR = 1
ASR = 2
ROR = 3

CODES = (LSL, LSR, ASR, ROR)


def _check(code: int) -> None:
    if code not in CODES:
        raise ValueError(f"shift code {code} is not one of the two bit field's four values")


def _bit(value: int, place: int) -> bool:
    return bool(value >> place & 1)


def _asr(value: int, amount: int) -> int:
    if _bit(value, SIGN_BIT):
        return (value >> amount | ~0 << (32 - amount)) & WORD_MASK
    return value >> amount


def _ror(value: int, amount: int) -> int:
    return (value >> amount | value << (32 - amount)) & WORD_MASK


def _between_one_and_thirty_one(code: int, value: int, amount: int) -> tuple[int, bool]:
    if code == LSL:
        return (value << amount) & WORD_MASK, _bit(value, 32 - amount)
    if code == LSR:
        return value >> amount, _bit(value, amount - 1)
    if code == ASR:
        return _asr(value, amount), _bit(value, amount - 1)
    return _ror(value, amount), _bit(value, amount - 1)


def by_amount(code: int, value: int, amount: int, carry: bool) -> tuple[int, bool]:
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

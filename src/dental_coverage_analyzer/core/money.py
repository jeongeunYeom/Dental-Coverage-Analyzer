from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re


@dataclass(frozen=True, slots=True)
class ParsedMoney:
    value: int
    raw: str


_NUMBER = r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_FULL_AMOUNT = re.compile(
    rf"^\s*(?:(?P<eok>{_NUMBER})\s*억)?\s*(?:(?P<man>{_NUMBER})\s*만(?:원)?)?\s*(?:(?P<won>{_NUMBER})\s*원)?\s*$"
)


def _decimal(value: str | None) -> Decimal:
    if value is None:
        return Decimal(0)
    return Decimal(value.replace(",", ""))


def parse_money(raw: str | None) -> ParsedMoney | None:
    """한국식 금액 표현을 원 단위로 변환하며 입력 원문을 보존한다.

    단위 없는 숫자는 금액으로 확정하지 않는다. 소수 원이 발생하는 표현도
    보험 원문의 정확성을 보존하기 위해 거부한다.
    """
    if raw is None or not raw.strip():
        return None
    normalized = raw.strip().replace("₩", "").replace(" ", "")
    if not any(unit in normalized for unit in ("억", "만", "원")):
        return None
    match = _FULL_AMOUNT.fullmatch(normalized)
    if not match or not any(match.groupdict().values()):
        return None
    try:
        amount = (
            _decimal(match.group("eok")) * Decimal(100_000_000)
            + _decimal(match.group("man")) * Decimal(10_000)
            + _decimal(match.group("won"))
        )
    except InvalidOperation:
        return None
    if amount != amount.to_integral_value():
        return None
    return ParsedMoney(value=int(amount), raw=raw)

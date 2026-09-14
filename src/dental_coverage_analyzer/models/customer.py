from dataclasses import dataclass
from datetime import date


@dataclass(slots=True)
class CustomerInfo:
    name: str | None = None
    masked_name: str | None = None
    age: int | None = None
    gender: str | None = None
    birth_date: date | None = None
    analysis_date: date | None = None

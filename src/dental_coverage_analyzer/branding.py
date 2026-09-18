from __future__ import annotations

from dataclasses import dataclass, asdict


DEFAULT_PRIMARY_COLOR = "#625EF5"


@dataclass(slots=True)
class BrandingSettings:
    company_name: str = ""
    consultant_name: str = ""
    phone: str = ""
    email: str = ""
    logo_path: str = ""
    footer_text: str = ""
    primary_color: str = DEFAULT_PRIMARY_COLOR
    onboarding_completed: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def has_contact_details(self) -> bool:
        return any((self.company_name, self.consultant_name, self.phone, self.email))

from __future__ import annotations

from dental_coverage_analyzer.branding import DEFAULT_PRIMARY_COLOR, BrandingSettings


REPORT_PRIMARY = "#234A75"
REPORT_PRIMARY_DARK = "#1C3D63"

REPORT_COLORS = {
    "primary": REPORT_PRIMARY,
    "primary_dark": REPORT_PRIMARY_DARK,
    "blue": "#4F7CAC",
    "sky": "#DCEAF7",
    "success": "#2E8B57",
    "success_bg": "#EAF7F0",
    "warning": "#D68A00",
    "warning_bg": "#FFF6E5",
    "danger": "#E15759",
    "danger_bg": "#FEF3F2",
    "purple": "#7C6FF0",
    "purple_bg": "#F1F0FF",
    "background": "#F7F9FC",
    "surface": "#FFFFFF",
    "border": "#D9E2EC",
    "text": "#1F2937",
    "secondary": "#667085",
    "muted": "#98A2B3",
}

CATEGORY_COLORS = {
    "보철치료": "#4F7CAC",
    "보존치료": "#2E8B57",
    "근관/치수치료": "#F59E0B",
    "치주치료": "#4BC9A7",
    "발치": "#E15759",
    "검사/영상": "#7C6FF0",
    "예방": "#55C1D9",
    "기타 치과": "#8B91A1",
}
DEFAULT_COLOR = "#8B91A1"

STATUS_STYLES = {
    "충분": ("#EAF7F0", "#2E8B57"),
    "부족": ("#FFF6E5", "#D68A00"),
    "미가입": ("#FEF3F2", "#D92D20"),
    "확인 필요": ("#FFF6E5", "#9A6700"),
    "정보 확인 필요": ("#FFF6E5", "#9A6700"),
    "정보 없음": ("#F2F4F7", "#667085"),
}
DEFAULT_STATUS_STYLE = ("#F2F4F7", "#667085")

SEVERITY_STYLES = {
    "INFO": ("#EAF2FB", "#234A75", "안내"),
    "WARNING": ("#FFF6E5", "#9A6700", "주의"),
    "ERROR": ("#FEF3F2", "#D92D20", "오류"),
}


def report_primary_color(branding: BrandingSettings) -> str:
    """Use a complete navy default unless the user intentionally branded the report."""
    has_branding = (
        branding.has_contact_details
        or bool(branding.logo_path)
        or bool(branding.footer_text.strip())
        or branding.primary_color != DEFAULT_PRIMARY_COLOR
    )
    return branding.primary_color if has_branding else REPORT_PRIMARY


def status_style(status: str | None, *, needs_review: bool = False) -> tuple[str, str]:
    if needs_review and status not in {"부족", "미가입"}:
        return STATUS_STYLES["확인 필요"]
    return STATUS_STYLES.get(status or "정보 없음", DEFAULT_STATUS_STYLE)

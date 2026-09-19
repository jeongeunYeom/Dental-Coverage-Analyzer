from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QGroupBox, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QVBoxLayout,
)

from dental_coverage_analyzer.branding import BrandingSettings

from .settings_store import copy_brand_logo


class BrandingSettingsDialog(QDialog):
    def __init__(self, settings: BrandingSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("보고서/브랜드 설정"); self.resize(620, 650)
        self._logo_path = settings.logo_path
        root = QVBoxLayout(self); root.setContentsMargins(20, 18, 20, 18); root.setSpacing(12)
        company_group = QGroupBox("회사 정보"); company_form = QFormLayout(company_group)
        design_group = QGroupBox("보고서 디자인"); design_form = QFormLayout(design_group)
        self.company = QLineEdit(settings.company_name); self.consultant = QLineEdit(settings.consultant_name)
        self.phone = QLineEdit(settings.phone); self.email = QLineEdit(settings.email)
        self.footer = QTextEdit(settings.footer_text); self.footer.setMaximumHeight(80)
        self.color = QLineEdit(settings.primary_color); self.color.setReadOnly(True)
        color_button = QPushButton("색상 선택"); color_button.clicked.connect(self._choose_color)
        color_row = QHBoxLayout(); color_row.addWidget(self.color); color_row.addWidget(color_button)
        logo_button = QPushButton("PNG/JPG 선택"); logo_button.clicked.connect(self._choose_logo)
        self.logo_name = QLabel(Path(self._logo_path).name if self._logo_path else "선택 안 함")
        logo_row = QHBoxLayout(); logo_row.addWidget(self.logo_name, 1); logo_row.addWidget(logo_button)
        company_form.addRow("회사명", self.company); company_form.addRow("담당자", self.consultant)
        company_form.addRow("연락처", self.phone); company_form.addRow("이메일", self.email)
        design_form.addRow("로고", logo_row); design_form.addRow("대표색", color_row)
        design_form.addRow("하단 문구", self.footer)
        root.addWidget(company_group); root.addWidget(design_group)
        root.addWidget(QLabel("미리보기")); self.preview = QLabel(); self.preview.setMinimumHeight(130)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter); self.preview.setObjectName("brandPreview"); root.addWidget(self.preview)
        for edit in (self.company, self.consultant, self.phone, self.email, self.color): edit.textChanged.connect(self._update_preview)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save); save_button.setText("저장"); save_button.setObjectName("primaryButton"); save_button.setProperty("buttonRole", "primary")
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel); cancel_button.setText("취소"); cancel_button.setProperty("buttonRole", "secondary")
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); root.addWidget(buttons)
        self._update_preview()

    @property
    def settings(self) -> BrandingSettings:
        return BrandingSettings(
            self.company.text(), self.consultant.text(), self.phone.text(), self.email.text(),
            self._logo_path, self.footer.toPlainText(), self.color.text(), True,
        )

    def _choose_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "로고 이미지 선택", "", "이미지 (*.png *.jpg *.jpeg)")
        if not path: return
        if QPixmap(path).isNull():
            QMessageBox.warning(self, "로고 이미지", "이미지 파일을 사용할 수 없습니다."); return
        try: self._logo_path = str(copy_brand_logo(path))
        except (OSError, ValueError): QMessageBox.warning(self, "로고 이미지", "이미지 파일을 사용할 수 없습니다."); return
        self.logo_name.setText(Path(self._logo_path).name); self._update_preview()

    def _choose_color(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.color.text()), self, "대표 색상 선택")
        if chosen.isValid(): self.color.setText(chosen.name().upper())

    def _update_preview(self) -> None:
        details = " · ".join(filter(None, (self.consultant.text(), self.phone.text(), self.email.text())))
        self.preview.setText(f"<b style='font-size:18px;color:{self.color.text()}'>{self.company.text() or '브랜드 미리보기'}</b><br>{details}")
        self.preview.setStyleSheet("background:white;border:1px solid #E8EAF2;border-radius:12px;padding:16px")

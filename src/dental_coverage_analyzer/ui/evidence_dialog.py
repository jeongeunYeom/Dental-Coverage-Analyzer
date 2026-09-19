from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton, QTextBrowser, QVBoxLayout

from .evidence import Evidence


class EvidenceDialog(QDialog):
    def __init__(self, evidence: Evidence, pdf_path: str, pdf_available: bool, parent=None) -> None:
        super().__init__(parent); self.setWindowTitle("원본 근거 보기"); self.resize(650, 480)
        layout = QVBoxLayout(self)
        pages = ", ".join(f"{page}페이지" for page in evidence.pages) or "페이지 정보 없음"
        layout.addWidget(QLabel(f"<b>출처 페이지</b><br>{pages}"))
        layout.addWidget(QLabel(f"<b>분석 신뢰도</b><br>{evidence.confidence}"))
        layout.addWidget(QLabel("<b>원본 내용</b>"))
        browser = QTextBrowser(); browser.setPlainText("\n\n".join(f"[{page}페이지]\n{text}" for page, text in evidence.entries) or "원본 문구 정보가 없습니다.")
        layout.addWidget(browser)
        if not pdf_available: layout.addWidget(QLabel("원본 PDF 파일을 찾을 수 없습니다."))
        open_button = QPushButton("원본 PDF 열기"); open_button.setEnabled(pdf_available)
        open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(pdf_path))); layout.addWidget(open_button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

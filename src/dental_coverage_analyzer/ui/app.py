from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QStackedWidget,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from dental_coverage_analyzer.core.pdf import PDFAnalysisResult, analyze_pdf
from dental_coverage_analyzer.models import Confidence
from dental_coverage_analyzer.reports import build_report_data, export_report_pdf, format_money, render_report_html
from dental_coverage_analyzer.reports.theme import CATEGORY_COLORS, DEFAULT_COLOR

from .session import (
    AnalysisSession, cause_label, optional_text, parse_cause, parse_optional_int,
    parse_payment_unit, payment_label,
)


APP_TITLE = "치아보험 보장분석표 생성기"


class DropArea(QFrame):
    selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        layout = QVBoxLayout(self)
        icon = QLabel("🦷")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("font-size:44px")
        text = QLabel("보험 보장분석 PDF를 여기에 끌어놓거나 클릭하여 선택하세요")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text.setWordWrap(True)
        layout.addStretch(); layout.addWidget(icon); layout.addWidget(text); layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit("")

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].toLocalFile().lower().endswith(".pdf"):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.selected.emit(event.mimeData().urls()[0].toLocalFile())
        event.acceptProposedAction()


class AnalysisThread(QThread):
    progress = Signal(int, str)
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, path: str) -> None:
        super().__init__()
        self.path = path

    def run(self) -> None:
        stages = {"TEXT_LAYER": "Text Layer 분석 중", "OCR": "OCR 처리 중"}
        try:
            def callback(current: int, total: int, stage: str) -> None:
                if stage == "PARSING":
                    self.progress.emit(84, "보험상품 확인 중")
                    self.progress.emit(92, "치아담보 추출 중")
                    return
                base = int((current - 1) / max(total, 1) * 80)
                bonus = {"TEXT_LAYER": 5, "OCR": 12, "PARSING": 95}.get(stage, 0)
                self.progress.emit(min(max(base + bonus, 1), 98), stages.get(stage, "분석 중"))
            result = analyze_pdf(self.path, on_progress=callback, is_cancelled=self.isInterruptionRequested)
            self.progress.emit(98, "결과 정리 중")
            self.progress.emit(100, "분석 완료")
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(_friendly_error(exc))


def _friendly_error(exc: Exception) -> str:
    message = str(exc).strip()
    if "PyMuPDF" in message:
        return "PDF 분석 구성요소를 사용할 수 없습니다. 프로그램을 다시 설치해 주세요."
    if "암호" in message:
        return "암호화된 PDF입니다. 암호가 없는 PDF로 다시 저장한 후 시도해 주세요."
    return f"PDF 분석을 완료하지 못했습니다. 파일을 확인한 후 다시 시도해 주세요.\n\n{message or '알 수 없는 오류'}"


class PreviewWindow(QMainWindow):
    def __init__(self, html: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("치아보험 보장분석표 미리보기")
        self.resize(900, 900)
        browser = QTextBrowser()
        browser.setHtml(html)
        self.setCentralWidget(browser)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 820)
        self.path: str | None = None
        self.session: AnalysisSession | None = None
        self.worker: AnalysisThread | None = None
        self.preview_window: PreviewWindow | None = None
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.start_page = self._build_start_page()
        self.result_page = QWidget()
        self.stack.addWidget(self.start_page)
        self.stack.addWidget(self.result_page)
        self._apply_style()

    def _build_start_page(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(90, 60, 90, 60)
        title = QLabel(APP_TITLE); title.setObjectName("title")
        subtitle = QLabel("보험 보장분석 PDF에서 확인 가능한 치아 관련 정보만 로컬에서 정리합니다.")
        subtitle.setObjectName("subtitle")
        self.drop = DropArea(); self.drop.selected.connect(self.select_pdf)
        self.file_label = QLabel("선택된 PDF 없음"); self.file_label.setObjectName("fileLabel")
        buttons = QHBoxLayout()
        choose = QPushButton("PDF 선택"); choose.clicked.connect(lambda: self.select_pdf(""))
        self.analyze_button = QPushButton("분석 시작"); self.analyze_button.setEnabled(False); self.analyze_button.clicked.connect(self.start_analysis)
        buttons.addWidget(choose); buttons.addWidget(self.analyze_button)
        self.progress = QProgressBar(); self.progress.hide()
        self.progress_label = QLabel(""); self.progress_label.hide()
        layout.addWidget(title); layout.addWidget(subtitle); layout.addSpacing(25); layout.addWidget(self.drop, 1)
        layout.addWidget(self.file_label); layout.addLayout(buttons); layout.addWidget(self.progress_label); layout.addWidget(self.progress)
        return page

    def select_pdf(self, path: str = "") -> None:
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "보험 보장분석 PDF 선택", "", "PDF 파일 (*.pdf)")
        if path:
            self.path = path; self.file_label.setText(Path(path).name); self.analyze_button.setEnabled(True)

    def start_analysis(self) -> None:
        if not self.path: return
        self.analyze_button.setEnabled(False); self.progress.show(); self.progress_label.show()
        self.progress.setValue(1); self.progress_label.setText("PDF 읽는 중")
        self.worker = AnalysisThread(self.path)
        self.worker.progress.connect(lambda value, text: (self.progress.setValue(value), self.progress_label.setText(text)))
        self.worker.completed.connect(self.analysis_completed)
        self.worker.failed.connect(self.analysis_failed)
        self.worker.start()

    def analysis_failed(self, message: str) -> None:
        self.analyze_button.setEnabled(True)
        QMessageBox.warning(self, "분석 실패", message)

    def analysis_completed(self, result: PDFAnalysisResult) -> None:
        self.session = AnalysisSession.from_result(self.path or "", result)
        self._build_result_page(); self.stack.setCurrentWidget(self.result_page)
        if any(issue.code == "OCR_NOT_AVAILABLE" for issue in result.validation_issues):
            QMessageBox.information(self, "OCR 제한", "OCR을 사용할 수 없어 일부 페이지는 수동 확인이 필요합니다.")

    def _build_result_page(self) -> None:
        old = self.result_page
        self.result_page = QWidget(); root = QVBoxLayout(self.result_page); root.setContentsMargins(24, 18, 24, 18)
        top = QHBoxLayout(); heading = QLabel("분석 결과"); heading.setObjectName("sectionTitle")
        self.customer_name = QLineEdit(); self.customer_name.setPlaceholderText("고객명 직접 입력 (선택)")
        top.addWidget(heading); top.addStretch(); top.addWidget(QLabel("고객명")); top.addWidget(self.customer_name)
        root.addLayout(top)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._summary_tab(), "전체 요약")
        self.tabs.addTab(self._contracts_tab(), "치아보험 상품")
        self.tabs.addTab(self._riders_tab(), "세부 치아담보")
        self.tabs.addTab(self._issues_tab(), "확인 필요")
        self.tabs.addTab(self._source_tab(), "원본 정보")
        actions = QHBoxLayout(); back = QPushButton("다른 PDF 분석"); back.clicked.connect(lambda: self.stack.setCurrentWidget(self.start_page))
        debug = QPushButton("Debug JSON 저장"); debug.clicked.connect(self.save_debug)
        preview = QPushButton("보고서 미리보기"); preview.clicked.connect(self.preview_report)
        save = QPushButton("PDF 저장"); save.setObjectName("primaryButton"); save.clicked.connect(self.save_report)
        actions.addWidget(back); actions.addWidget(debug); actions.addStretch(); actions.addWidget(preview); actions.addWidget(save); root.addLayout(actions)
        self.stack.addWidget(self.result_page); self.stack.removeWidget(old); old.deleteLater()

    def _summary_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); cards = QWidget(); cards_layout = QVBoxLayout(cards)
        for item in self.session.aggregates:
            card = QFrame(); card.setObjectName("card"); row = QHBoxLayout(card)
            color = CATEGORY_COLORS.get(item.category or "", DEFAULT_COLOR)
            name = QLabel(item.raw_name); name.setStyleSheet(f"font-size:18px;font-weight:700;color:{color}")
            row.addWidget(name, 2)
            for label, value in (("가입금액", format_money(item.enrolled_amount)), ("권장금액", format_money(item.recommended_amount)), ("보장률", f"{item.calculate_ratio():.0f}%" if item.calculate_ratio() is not None else "정보 없음"), ("상태", item.status or "확인 필요")):
                box = QLabel(f"<span style='color:#7B8297'>{label}</span><br><b>{value}</b>"); row.addWidget(box, 1)
            cards_layout.addWidget(card)
        cards_layout.addStretch(); scroll.setWidget(cards); layout.addWidget(scroll, 1)
        self.aggregate_table = self._table(["담보명", "카테고리", "권장금액(원)", "가입금액(원)", "부족금액(원)", "상태", "출처 페이지", "confidence"])
        self._fill_aggregates(); layout.addWidget(self.aggregate_table, 1)
        layout.addLayout(self._add_delete_buttons("Aggregate 추가", self.add_aggregate, "선택 Aggregate 삭제", self.delete_aggregate))
        return widget

    def _contracts_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.contract_table = self._table(["보험사", "상품명", "가입일", "보험기간", "월보험료(원)", "납입기간", "납입주기", "만기", "출처 페이지", "confidence"])
        for row, item in enumerate(self.session.contracts):
            self.contract_table.insertRow(row)
            values = [item.insurer, item.product_name, item.enrollment_date.isoformat() if item.enrollment_date else None, item.coverage_period, item.monthly_premium, item.payment_period, item.payment_cycle, item.maturity, ", ".join(str(s.page) for s in item.sources), {"HIGH":"높음","MEDIUM":"보통","LOW":"낮음"}.get(item.confidence.value, "확인 필요")]
            self._set_row(self.contract_table, row, values)
            raw = "\n\n".join(source.raw_text or "" for source in item.sources)
            for col in range(self.contract_table.columnCount()): self.contract_table.item(row, col).setToolTip(raw)
        layout.addWidget(self.contract_table)
        return widget

    def _riders_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.rider_table = self._table(["담보명", "카테고리", "보험사", "상품명", "가입금액(원)", "질병/상해", "지급단위", "출처 페이지", "confidence"])
        self._fill_riders(); layout.addWidget(self.rider_table)
        layout.addLayout(self._add_delete_buttons("Rider 추가", self.add_rider, "선택 Rider 삭제", self.delete_rider))
        return widget

    def _issues_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        table = self._table(["등급", "코드", "확인할 내용", "페이지"]); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        for row, issue in enumerate(self.session.result.validation_issues):
            severity = {"INFO":"안내", "WARNING":"주의", "ERROR":"오류"}.get(issue.severity.value, issue.severity.value)
            table.insertRow(row); self._set_row(table, row, [severity, issue.code, issue.message, ", ".join(map(str, issue.page_numbers))])
            color = QColor("#FFF1F2" if issue.severity.value == "ERROR" else "#FFF8E6")
            for col in range(table.columnCount()): table.item(row, col).setBackground(color)
        layout.addWidget(table); return widget

    def _source_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        result = self.session.result
        layout.addWidget(QLabel(f"원본 PDF: {self.session.source_path}"))
        layout.addWidget(QLabel(f"Provider: {result.provider} / 지원 수준: {result.support_summary.support_level.value if result.support_summary else '정보 없음'}"))
        browser = QTextBrowser(); browser.setPlainText("\n\n".join(
            f"[페이지 {p.page_number}] [최종 출처: {p.effective_source.value}]\n"
            f"--- Text Layer ---\n{p.text_layer_text or '(없음)'}\n"
            f"--- OCR ---\n{p.ocr_text or '(사용 안 함/실패)'}"
            for p in result.document.pages
        )); layout.addWidget(browser)
        open_button = QPushButton("원본 PDF 열기"); open_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.session.source_path))); layout.addWidget(open_button)
        return widget

    def _table(self, headers) -> QTableWidget:
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers); table.setAlternatingRowColors(True); table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); return table

    def _set_row(self, table, row, values) -> None:
        for col, value in enumerate(values): table.setItem(row, col, QTableWidgetItem("정보 없음" if value is None else str(value)))

    def _add_delete_buttons(self, add_text, add_slot, delete_text, delete_slot):
        layout = QHBoxLayout(); add = QPushButton(add_text); delete = QPushButton(delete_text); add.clicked.connect(add_slot); delete.clicked.connect(delete_slot); layout.addWidget(add); layout.addWidget(delete); layout.addStretch(); return layout

    def _fill_aggregates(self):
        self.aggregate_table.setRowCount(0)
        for row, item in enumerate(self.session.aggregates):
            confidence = {"HIGH":"높음","MEDIUM":"보통","LOW":"낮음"}.get(item.confidence.value, "확인 필요")
            self.aggregate_table.insertRow(row); self._set_row(self.aggregate_table, row, [item.raw_name, item.category, item.recommended_amount, item.enrolled_amount, item.normalized_shortage if item.normalized_shortage is not None else item.shortage_amount, item.status, ", ".join(map(str, item.source_pages)), confidence])
            raw = item.representative_source.raw_text if item.representative_source else ""
            for col in range(self.aggregate_table.columnCount()): self.aggregate_table.item(row, col).setToolTip(raw or "")

    def _fill_riders(self):
        self.rider_table.setRowCount(0)
        for row, item in enumerate(self.session.riders):
            pages = sorted({source.page for source in item.sources} | ({item.source.page} if item.source else set()))
            confidence = {"HIGH": "높음", "MEDIUM": "보통", "LOW": "낮음"}.get(item.confidence.value, "확인 필요")
            self.rider_table.insertRow(row); self._set_row(self.rider_table, row, [item.raw_name, item.category, item.insurer, item.product_name, item.enrolled_amount, cause_label(item.cause_type), payment_label(item.payment_unit), ", ".join(map(str, pages)), confidence])
            for col in range(self.rider_table.columnCount()): self.rider_table.item(row, col).setToolTip(item.raw_text or "")

    def add_aggregate(self): self.session.add_aggregate(); self._fill_aggregates()
    def add_rider(self): self.session.add_rider(); self._fill_riders()
    def delete_aggregate(self):
        row = self.aggregate_table.currentRow()
        if row >= 0: self.session.aggregates.pop(row); self._fill_aggregates()
    def delete_rider(self):
        row = self.rider_table.currentRow()
        if row >= 0: self.session.riders.pop(row); self._fill_riders()

    def _sync_tables(self) -> bool:
        try:
            self.session.customer.name = self.customer_name.text().strip() or None
            for row, item in enumerate(self.session.aggregates):
                item.raw_name = self.aggregate_table.item(row, 0).text(); item.category = optional_text(self.aggregate_table.item(row, 1).text())
                item.recommended_amount = parse_optional_int(self.aggregate_table.item(row, 2).text()); item.enrolled_amount = parse_optional_int(self.aggregate_table.item(row, 3).text())
                item.shortage_amount = parse_optional_int(self.aggregate_table.item(row, 4).text()); item.normalized_shortage = item.shortage_amount; item.status = optional_text(self.aggregate_table.item(row, 5).text())
            for row, item in enumerate(self.session.contracts):
                item.insurer = optional_text(self.contract_table.item(row, 0).text()); item.product_name = optional_text(self.contract_table.item(row, 1).text()); item.coverage_period = optional_text(self.contract_table.item(row, 3).text())
                item.monthly_premium = parse_optional_int(self.contract_table.item(row, 4).text()); item.payment_period = optional_text(self.contract_table.item(row, 5).text()); item.payment_cycle = optional_text(self.contract_table.item(row, 6).text()); item.maturity = optional_text(self.contract_table.item(row, 7).text())
            for row, item in enumerate(self.session.riders):
                item.raw_name = self.rider_table.item(row, 0).text(); item.category = optional_text(self.rider_table.item(row, 1).text()); item.insurer = optional_text(self.rider_table.item(row, 2).text()); item.product_name = optional_text(self.rider_table.item(row, 3).text())
                item.enrolled_amount = parse_optional_int(self.rider_table.item(row, 4).text()); item.cause_type = parse_cause(self.rider_table.item(row, 5).text()); item.payment_unit = parse_payment_unit(self.rider_table.item(row, 6).text())
            return True
        except (ValueError, AttributeError) as exc:
            QMessageBox.warning(self, "입력값 확인", f"금액은 숫자(원 단위)로 입력해 주세요.\n{exc}"); return False

    def report_data(self):
        if not self._sync_tables(): return None
        return build_report_data(self.session.customer, self.session.aggregates, self.session.contracts, self.session.riders)

    def preview_report(self):
        data = self.report_data()
        if data: self.preview_window = PreviewWindow(render_report_html(data), self); self.preview_window.show()

    def save_report(self):
        data = self.report_data()
        if not data: return
        path, _ = QFileDialog.getSaveFileName(self, "치아보험 보장분석표 저장", "치아보험_보장분석표.pdf", "PDF 파일 (*.pdf)")
        if path:
            try: export_report_pdf(data, path); QMessageBox.information(self, "저장 완료", f"보고서를 저장했습니다.\n{path}")
            except Exception as exc: QMessageBox.warning(self, "저장 실패", f"PDF 저장 중 오류가 발생했습니다.\n{exc}")

    def save_debug(self):
        path, _ = QFileDialog.getSaveFileName(self, "Debug JSON 저장", "analysis_debug.json", "JSON (*.json)")
        if path: self.session.result.export_json(path)

    def _apply_style(self):
        self.setStyleSheet("""
        QMainWindow,QWidget { background:#F7F8FC; color:#262A40; font-family:'Malgun Gothic'; font-size:13px; }
        #title { font-size:30px; font-weight:800; color:#252943; } #subtitle,#fileLabel { color:#737A91; }
        #dropArea { background:white; border:2px dashed #B7B5FA; border-radius:18px; min-height:280px; }
        QPushButton { background:white; border:1px solid #DADDEA; border-radius:9px; padding:10px 18px; font-weight:600; }
        QPushButton:hover { border-color:#625EF5; } #primaryButton { background:#625EF5; color:white; border:none; }
        #sectionTitle { font-size:24px; font-weight:800; } #card { background:white; border:1px solid #E6E7EF; border-radius:14px; padding:8px; }
        QTabWidget::pane { border:1px solid #E2E4EE; background:white; border-radius:10px; }
        QTabBar::tab { padding:11px 18px; } QTabBar::tab:selected { color:#625EF5; font-weight:700; }
        QTableWidget { background:white; border:0; gridline-color:#ECEEF4; } QHeaderView::section { background:#F0F1F7; padding:8px; border:0; font-weight:700; }
        QLineEdit { background:white; border:1px solid #DADDEA; border-radius:8px; padding:8px; }
        QProgressBar { border:0; border-radius:6px; background:#E6E7F0; height:12px; } QProgressBar::chunk { border-radius:6px; background:#625EF5; }
        """)


def run_gui() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_TITLE)
    window = MainWindow(); window.show()
    return app.exec()

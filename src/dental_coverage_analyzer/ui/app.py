from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QProgressBar, QPushButton, QScrollArea, QStackedWidget,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from dental_coverage_analyzer.core.pdf import PDFAnalysisResult, analyze_pdf
from dental_coverage_analyzer.branding import BrandingSettings
from dental_coverage_analyzer.core.processing import normalize_aggregate_values
from dental_coverage_analyzer.models import Confidence
from dental_coverage_analyzer.reports import (
    build_report_data, export_report_pdf, format_money, render_report_html,
    select_dental_report_contracts,
)
from dental_coverage_analyzer.reports.theme import CATEGORY_COLORS, DEFAULT_COLOR

from .session import (
    AnalysisSession, cause_label, optional_text, parse_cause, parse_optional_int,
    parse_payment_unit, payment_label,
)
from .project_store import (
    FutureProjectVersionError, ProjectError, autosave_path, delete_autosave,
    load_project, load_recent_projects, remember_project, remove_recent_project,
    save_project as save_project_file, app_version,
)
from .settings_store import load_settings, save_settings
from .settings_dialog import BrandingSettingsDialog
from .evidence import aggregate_evidence, contract_evidence, rider_evidence
from .evidence_dialog import EvidenceDialog
from .presentation import confidence_label, issue_label


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
        stages = {"TEXT_LAYER": "PDF 내용 읽는 중", "OCR": "스캔 문서 읽는 중"}
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
    def __init__(self, *, enable_startup_prompts: bool = True) -> None:
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 820)
        self.path: str | None = None
        self.session: AnalysisSession | None = None
        self.worker: AnalysisThread | None = None
        self.preview_window: PreviewWindow | None = None
        self._deferred_autosave = False
        self.branding = load_settings()
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.start_page = self._build_start_page()
        self.result_page = QWidget()
        self.stack.addWidget(self.start_page)
        self.stack.addWidget(self.result_page)
        self._setup_project_menu()
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(30_000)
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start()
        self._apply_style()
        # Startup prompts are enabled for the real application.  Tests and other
        # non-interactive embedders can explicitly disable them without changing
        # the persisted onboarding/recovery behaviour used by end users.
        if enable_startup_prompts:
            QTimer.singleShot(0, self._check_autosave_recovery)
        if enable_startup_prompts and not self.branding.onboarding_completed:
            QTimer.singleShot(50, self._show_onboarding)

    def _setup_project_menu(self) -> None:
        menu = self.menuBar().addMenu("파일")
        open_action = QAction("프로젝트 열기", self); open_action.setShortcut(QKeySequence.StandardKey.Open); open_action.triggered.connect(self.open_project)
        save_action = QAction("프로젝트 저장", self); save_action.setShortcut(QKeySequence.StandardKey.Save); save_action.triggered.connect(self.save_project)
        save_as_action = QAction("다른 이름으로 저장", self); save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S")); save_as_action.triggered.connect(lambda _checked=False: self.save_project(save_as=True))
        menu.addAction(open_action); menu.addAction(save_action); menu.addAction(save_as_action)
        self.recent_menu = menu.addMenu("최근 프로젝트")
        self._refresh_recent_menu()
        settings_menu = self.menuBar().addMenu("설정")
        settings_menu.addAction("보고서/브랜드 설정", self.open_branding_settings)
        tools = self.menuBar().addMenu("도구"); advanced = tools.addMenu("고급 기능")
        advanced.addAction("진단 데이터 저장", self.save_debug)
        help_menu = self.menuBar().addMenu("도움말")
        help_menu.addAction("사용 방법", self.show_help); help_menu.addAction("프로그램 정보", self.show_about)

    def _refresh_recent_menu(self) -> None:
        self.recent_menu.clear()
        recent = load_recent_projects()
        if not recent:
            action = self.recent_menu.addAction("없음"); action.setEnabled(False); return
        for path in recent:
            action = self.recent_menu.addAction(path)
            action.triggered.connect(lambda _checked=False, value=path: self.open_project(value))

    def _build_start_page(self) -> QWidget:
        page = QWidget(); layout = QVBoxLayout(page); layout.setContentsMargins(90, 60, 90, 60)
        title = QLabel("치아보험 보장분석"); title.setObjectName("title")
        subtitle = QLabel("보험 보장분석 PDF에서 치아 관련 보장내용을 자동으로 정리하고\n고객용 보고서를 생성합니다.")
        subtitle.setObjectName("subtitle")
        self.drop = DropArea(); self.drop.selected.connect(self.select_pdf)
        self.file_label = QLabel("선택된 PDF 없음"); self.file_label.setObjectName("fileLabel")
        buttons = QHBoxLayout()
        choose = QPushButton("PDF 선택"); choose.clicked.connect(lambda: self.select_pdf(""))
        open_project = QPushButton("프로젝트 열기"); open_project.clicked.connect(self.open_project)
        self.analyze_button = QPushButton("분석 시작"); self.analyze_button.setEnabled(False); self.analyze_button.clicked.connect(self.start_analysis)
        buttons.addWidget(choose); buttons.addWidget(open_project); buttons.addWidget(self.analyze_button)
        self.progress = QProgressBar(); self.progress.hide()
        self.progress_label = QLabel(""); self.progress_label.hide()
        layout.addWidget(title); layout.addWidget(subtitle); layout.addSpacing(25); layout.addWidget(self.drop, 1)
        layout.addWidget(self.file_label); layout.addLayout(buttons); layout.addWidget(self.progress_label); layout.addWidget(self.progress)
        privacy = QLabel("모든 분석은 이 PC에서 처리됩니다."); privacy.setObjectName("subtitle"); privacy.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(privacy)
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
        self.session.is_dirty = True
        self._build_result_page(); self.stack.setCurrentWidget(self.result_page); self._update_window_title()
        if any(issue.code == "OCR_NOT_AVAILABLE" for issue in result.validation_issues):
            QMessageBox.information(self, "OCR 제한", "OCR을 사용할 수 없어 일부 페이지는 수동 확인이 필요합니다.")

    def _build_result_page(self) -> None:
        old = self.result_page
        self.result_page = QWidget(); root = QVBoxLayout(self.result_page); root.setContentsMargins(24, 18, 24, 18)
        top = QHBoxLayout(); heading = QLabel("분석 결과"); heading.setObjectName("sectionTitle")
        self.customer_name = QLineEdit(); self.customer_name.setPlaceholderText("고객명 직접 입력 (선택)")
        self.customer_name.setText(self.session.customer.name or "")
        top.addWidget(heading); top.addStretch(); top.addWidget(QLabel("고객명")); top.addWidget(self.customer_name)
        root.addLayout(top)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._summary_tab(), "전체 요약")
        self.tabs.addTab(self._contracts_tab(), "치아보험 상품")
        self.tabs.addTab(self._riders_tab(), "세부 치아담보")
        self.tabs.addTab(self._issues_tab(), "확인 필요")
        self.tabs.addTab(self._source_tab(), "원본 정보")
        root.addWidget(QLabel("상담 코멘트"))
        self.comment_edit = QTextEdit()
        self.comment_edit.setPlaceholderText("보고서에 함께 표시할 코멘트를 입력하세요.")
        self.comment_edit.setPlainText(self.session.comment)
        self.comment_edit.setMaximumHeight(100)
        root.addWidget(self.comment_edit)
        actions = QHBoxLayout(); back = QPushButton("새 분석"); back.clicked.connect(self.start_other_pdf)
        preview = QPushButton("보고서 미리보기"); preview.clicked.connect(self.preview_report)
        save = QPushButton("PDF 저장"); save.setObjectName("primaryButton"); save.clicked.connect(self.save_report)
        actions.addWidget(back); actions.addStretch(); actions.addWidget(preview); actions.addWidget(save); root.addLayout(actions)
        self._connect_dirty_signals()
        self.stack.addWidget(self.result_page); self.stack.removeWidget(old); old.deleteLater()

    def _connect_dirty_signals(self) -> None:
        self.customer_name.textChanged.connect(self._mark_dirty)
        self.comment_edit.textChanged.connect(self._mark_dirty)
        self.aggregate_table.cellChanged.connect(self._mark_dirty)
        self.contract_table.cellChanged.connect(self._mark_dirty)
        self.rider_table.cellChanged.connect(self._mark_dirty)

    def _mark_dirty(self, *_args) -> None:
        if self.session:
            self.session.mark_dirty()
            self._update_window_title()

    def _update_window_title(self) -> None:
        suffix = " *" if self.session and self.session.is_dirty else ""
        self.setWindowTitle(APP_TITLE + suffix)

    def _summary_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        scroll = QScrollArea(); scroll.setWidgetResizable(True); cards = QWidget(); cards_layout = QVBoxLayout(cards)
        for item in self.session.aggregates:
            normalized = normalize_aggregate_values(item)
            card = QFrame(); card.setObjectName("card"); row = QHBoxLayout(card)
            color = CATEGORY_COLORS.get(item.category or "", DEFAULT_COLOR)
            name = QLabel(item.raw_name); name.setStyleSheet(f"font-size:18px;font-weight:700;color:{color}")
            row.addWidget(name, 2)
            for label, value in (("가입금액", format_money(item.enrolled_amount)), ("권장금액", format_money(item.recommended_amount)), ("보장률", f"{normalized.ratio:.0f}%" if normalized.ratio is not None else "정보 없음"), ("상태", normalized.status)):
                box = QLabel(f"<span style='color:#7B8297'>{label}</span><br><b>{value}</b>"); row.addWidget(box, 1)
            cards_layout.addWidget(card)
        cards_layout.addStretch(); scroll.setWidget(cards); layout.addWidget(scroll, 1)
        self.aggregate_table = self._table(["담보명", "카테고리", "권장금액(원)", "가입금액(원)", "부족금액(원)", "상태", "출처 페이지", "분석 신뢰도"])
        self._fill_aggregates(); layout.addWidget(self.aggregate_table, 1)
        buttons = self._add_delete_buttons("전체 보장 추가", self.add_aggregate, "선택 보장 삭제", self.delete_aggregate)
        evidence = QPushButton("원본 근거 보기"); evidence.clicked.connect(self.show_aggregate_evidence); buttons.addWidget(evidence)
        layout.addLayout(buttons)
        return widget

    def _contracts_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.contract_table = self._table(["보험사", "상품명", "가입일", "보험기간", "월보험료(원)", "납입기간", "납입주기", "만기", "출처 페이지", "분석 신뢰도"])
        self.dental_contracts = select_dental_report_contracts(self.session.contracts, self.session.riders)
        if not self.dental_contracts:
            empty = QLabel("없음"); empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("font-size:18px;font-weight:700;color:#858CA0;padding:24px")
            layout.addWidget(empty)
        for row, item in enumerate(self.dental_contracts):
            self.contract_table.insertRow(row)
            values = [item.insurer, item.product_name, item.enrollment_date.isoformat() if item.enrollment_date else None, item.coverage_period, item.monthly_premium, item.payment_period, item.payment_cycle, item.maturity, ", ".join(str(s.page) for s in item.sources), confidence_label(item.confidence)]
            self._set_row(self.contract_table, row, values)
            raw = "\n\n".join(source.raw_text or "" for source in item.sources)
            for col in range(self.contract_table.columnCount()): self.contract_table.item(row, col).setToolTip(raw)
        layout.addWidget(self.contract_table)
        evidence = QPushButton("원본 근거 보기"); evidence.clicked.connect(self.show_contract_evidence); layout.addWidget(evidence)
        return widget

    def _riders_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.rider_table = self._table(["담보명", "카테고리", "보험사", "상품명", "가입금액(원)", "질병/상해", "지급단위", "출처 페이지", "분석 신뢰도"])
        self._fill_riders(); layout.addWidget(self.rider_table)
        buttons = self._add_delete_buttons("세부 담보 추가", self.add_rider, "선택 세부 담보 삭제", self.delete_rider)
        evidence = QPushButton("원본 근거 보기"); evidence.clicked.connect(self.show_rider_evidence); buttons.addWidget(evidence)
        layout.addLayout(buttons)
        return widget

    def _issues_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        table = self._table(["등급", "구분", "확인할 내용", "페이지"]); table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        row = 0
        for issue in self.session.result.validation_issues:
            severity = {"INFO":"안내", "WARNING":"주의", "ERROR":"오류"}.get(issue.severity.value, issue.severity.value)
            table.insertRow(row); self._set_row(table, row, [severity, issue_label(issue.code), issue.message, ", ".join(map(str, issue.page_numbers))])
            color = QColor("#FFF1F2" if issue.severity.value == "ERROR" else "#FFF8E6")
            tooltip = "\n".join(issue.raw_values)
            for col in range(table.columnCount()):
                table.item(row, col).setBackground(color); table.item(row, col).setToolTip(tooltip)
            row += 1
        for warning in self.session.aggregate_conflict_warnings:
            table.insertRow(row); self._set_row(table, row, ["주의", "보장정보 확인 필요", warning, "상세 문구 참조"])
            for col in range(table.columnCount()): table.item(row, col).setBackground(QColor("#FFF8E6"))
            row += 1
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
        open_button.setEnabled(self.session.original_pdf_available)
        if not self.session.original_pdf_available:
            layout.insertWidget(1, QLabel("원본 PDF 파일을 찾을 수 없습니다. 기존 분석 결과는 계속 사용할 수 있습니다."))
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
            normalized = normalize_aggregate_values(item)
            confidence = confidence_label(item.confidence)
            self.aggregate_table.insertRow(row); self._set_row(self.aggregate_table, row, [item.raw_name, item.category, item.recommended_amount, item.enrolled_amount, normalized.shortage, normalized.status, ", ".join(map(str, item.source_pages)), confidence])
            raw = item.representative_source.raw_text if item.representative_source else ""
            for col in range(self.aggregate_table.columnCount()): self.aggregate_table.item(row, col).setToolTip(raw or "")

    def _fill_riders(self):
        self.rider_table.setRowCount(0)
        for row, item in enumerate(self.session.riders):
            pages = sorted({source.page for source in item.sources} | ({item.source.page} if item.source else set()))
            confidence = confidence_label(item.confidence)
            self.rider_table.insertRow(row); self._set_row(self.rider_table, row, [item.raw_name, item.category, item.insurer, item.product_name, item.enrolled_amount, cause_label(item.cause_type), payment_label(item.payment_unit), ", ".join(map(str, pages)), confidence])
            for col in range(self.rider_table.columnCount()): self.rider_table.item(row, col).setToolTip(item.raw_text or "")

    def add_aggregate(self): self.session.add_aggregate(); self._fill_aggregates(); self._mark_dirty()
    def add_rider(self): self.session.add_rider(); self._fill_riders(); self._mark_dirty()
    def delete_aggregate(self):
        row = self.aggregate_table.currentRow()
        if row >= 0:
            removed = self.session.aggregates.pop(row)
            self.session.raw_aggregate_candidates = [item for item in self.session.raw_aggregate_candidates if item is not removed]
            self._fill_aggregates(); self._mark_dirty()
    def delete_rider(self):
        row = self.rider_table.currentRow()
        if row >= 0: self.session.riders.pop(row); self._fill_riders(); self._mark_dirty()

    def _sync_tables(self) -> bool:
        try:
            self.session.customer.name = self.customer_name.text().strip() or None
            for row, item in enumerate(self.session.aggregates):
                item.raw_name = self.aggregate_table.item(row, 0).text(); item.category = optional_text(self.aggregate_table.item(row, 1).text())
                item.recommended_amount = parse_optional_int(self.aggregate_table.item(row, 2).text()); item.enrolled_amount = parse_optional_int(self.aggregate_table.item(row, 3).text())
                item.shortage_amount = parse_optional_int(self.aggregate_table.item(row, 4).text()); item.normalized_shortage = item.shortage_amount; item.status = optional_text(self.aggregate_table.item(row, 5).text())
            for row, item in enumerate(self.dental_contracts):
                item.insurer = optional_text(self.contract_table.item(row, 0).text()); item.product_name = optional_text(self.contract_table.item(row, 1).text()); item.coverage_period = optional_text(self.contract_table.item(row, 3).text())
                item.monthly_premium = parse_optional_int(self.contract_table.item(row, 4).text()); item.payment_period = optional_text(self.contract_table.item(row, 5).text()); item.payment_cycle = optional_text(self.contract_table.item(row, 6).text()); item.maturity = optional_text(self.contract_table.item(row, 7).text())
            for row, item in enumerate(self.session.riders):
                item.raw_name = self.rider_table.item(row, 0).text(); item.category = optional_text(self.rider_table.item(row, 1).text()); item.insurer = optional_text(self.rider_table.item(row, 2).text()); item.product_name = optional_text(self.rider_table.item(row, 3).text())
                item.enrolled_amount = parse_optional_int(self.rider_table.item(row, 4).text()); item.cause_type = parse_cause(self.rider_table.item(row, 5).text()); item.payment_unit = parse_payment_unit(self.rider_table.item(row, 6).text())
            self.session.comment = self.comment_edit.toPlainText()
            return True
        except (ValueError, AttributeError) as exc:
            QMessageBox.warning(self, "입력값 확인", f"금액은 숫자(원 단위)로 입력해 주세요.\n{exc}"); return False

    def report_data(self):
        if not self._sync_tables(): return None
        return build_report_data(
            self.session.customer,
            self.session.raw_aggregate_candidates or self.session.aggregates,
            self.session.contracts,
            self.session.riders,
            self.session.result.validation_issues if self.session.result else [],
            self.session.comment,
            self.branding,
        )

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
        if not self.session: return
        answer = QMessageBox.warning(self, "진단 데이터 저장", "진단 데이터에는 분석된 보험 정보가 포함될 수 있습니다.\n외부에 전달하기 전에 내용을 확인해 주세요.", QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
        if answer != QMessageBox.StandardButton.Ok: return
        path, _ = QFileDialog.getSaveFileName(self, "진단 데이터 저장", "analysis_diagnostic.json", "JSON (*.json)")
        if path: self.session.result.export_json(path)

    def open_branding_settings(self) -> None:
        dialog = BrandingSettingsDialog(self.branding, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            self.branding = dialog.settings
            try: save_settings(self.branding)
            except OSError: QMessageBox.warning(self, "설정 저장", "설정을 저장할 수 없습니다."); return
            self._apply_style()

    def _show_evidence(self, evidence) -> None:
        if self.session:
            EvidenceDialog(evidence, self.session.source_path, self.session.original_pdf_available, self).exec()

    def show_aggregate_evidence(self) -> None:
        row = self.aggregate_table.currentRow()
        if row < 0: QMessageBox.information(self, "원본 근거 보기", "확인할 전체 보장을 선택해 주세요."); return
        self._show_evidence(aggregate_evidence(self.session.aggregates[row]))

    def show_contract_evidence(self) -> None:
        row = self.contract_table.currentRow()
        if row < 0: QMessageBox.information(self, "원본 근거 보기", "확인할 보험상품을 선택해 주세요."); return
        self._show_evidence(contract_evidence(self.dental_contracts[row]))

    def show_rider_evidence(self) -> None:
        row = self.rider_table.currentRow()
        if row < 0: QMessageBox.information(self, "원본 근거 보기", "확인할 세부 담보를 선택해 주세요."); return
        self._show_evidence(rider_evidence(self.session.riders[row]))

    def _show_onboarding(self) -> None:
        QMessageBox.information(self, APP_TITLE, "1. 보험 보장분석 PDF 선택\n2. 분석 결과 확인 및 수정\n3. 상담 코멘트 작성\n4. PDF 보고서 저장\n\n모든 분석은 이 PC에서 처리됩니다.")
        self.branding.onboarding_completed = True
        try: save_settings(self.branding)
        except OSError: pass

    def show_help(self) -> None:
        QMessageBox.information(self, "사용 방법", "PDF를 선택해 분석한 뒤 결과를 확인·수정하세요.\nCtrl+S로 프로젝트를 저장하고, 미리보기 확인 후 PDF 보고서를 저장할 수 있습니다.")

    def show_about(self) -> None:
        QMessageBox.about(self, "프로그램 정보", f"{APP_TITLE}\n버전 {app_version()}\n\n보험 보장분석 자료의 치아 보장내용을 정리하는 로컬 프로그램입니다.\n모든 분석은 로컬에서 처리됩니다.")

    def save_project(self, _checked=False, save_as: bool = False) -> bool:
        if not self.session:
            QMessageBox.information(self, "프로젝트 저장", "먼저 PDF를 분석하거나 프로젝트를 열어 주세요.")
            return False
        if hasattr(self, "aggregate_table") and not self._sync_tables():
            return False
        destination = None if save_as else self.session.project_path
        if not destination:
            destination, _ = QFileDialog.getSaveFileName(self, "프로젝트 저장", "치아보험분석.dca", "Dental Coverage Analyzer 프로젝트 (*.dca)")
        if not destination:
            return False
        if not destination.lower().endswith(".dca"):
            destination += ".dca"
        try:
            project = save_project_file(
                self.session, destination, self.session.project_created_at, backup=True,
            )
        except Exception:
            QMessageBox.warning(self, "저장 실패", "프로젝트를 저장할 수 없습니다.")
            return False
        self.session.project_path = str(Path(destination).resolve())
        self.session.project_created_at = project.created_at
        self.session.is_dirty = False
        delete_autosave()
        remember_project(destination); self._refresh_recent_menu(); self._update_window_title()
        return True

    def open_project(self, path: str = "") -> None:
        if not self._confirm_unsaved_changes():
            return
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "프로젝트 열기", "", "Dental Coverage Analyzer 프로젝트 (*.dca)")
        if not path:
            return
        if not Path(path).is_file():
            QMessageBox.warning(self, "프로젝트 열기", "프로젝트 파일을 찾을 수 없습니다.")
            remove_recent_project(path); self._refresh_recent_menu(); return
        try:
            loaded = load_project(path)
        except FutureProjectVersionError as exc:
            QMessageBox.warning(self, "프로젝트 열기", str(exc)); return
        except ProjectError:
            QMessageBox.warning(self, "프로젝트 열기", "프로젝트 파일을 읽을 수 없습니다."); return
        self.session = loaded.session
        self.session.project_path = str(Path(path).resolve())
        self.session.project_created_at = loaded.project.created_at
        self.session.is_dirty = False
        self.path = self.session.source_path
        self._build_result_page(); self.stack.setCurrentWidget(self.result_page)
        remember_project(path); self._refresh_recent_menu(); self._update_window_title()
        if loaded.original_pdf_missing:
            QMessageBox.information(
                self, "원본 PDF 없음",
                "원본 PDF 파일을 찾을 수 없습니다.\n기존 분석 결과는 계속 사용할 수 있습니다.",
            )

    def _autosave(self) -> None:
        if not self.session or not self.session.is_dirty:
            return
        if hasattr(self, "aggregate_table") and not self._sync_tables():
            return
        try:
            save_project_file(self.session, autosave_path(), self.session.project_created_at, backup=False)
        except Exception:
            pass

    def _check_autosave_recovery(self) -> None:
        path = autosave_path()
        if not path.is_file():
            return
        answer = QMessageBox.question(
            self, "작업 자동복구",
            "이전에 저장되지 않은 작업이 있습니다.\n복구하시겠습니까?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            try:
                loaded = load_project(path)
            except ProjectError:
                QMessageBox.warning(self, "자동복구", "자동복구 파일을 읽을 수 없습니다.")
                return
            self.session = loaded.session; self.session.is_dirty = True
            self.path = self.session.source_path
            self._build_result_page(); self.stack.setCurrentWidget(self.result_page); self._update_window_title()
            if loaded.original_pdf_missing:
                QMessageBox.information(self, "원본 PDF 없음", "원본 PDF 파일을 찾을 수 없습니다.\n기존 분석 결과는 계속 사용할 수 있습니다.")
        elif answer == QMessageBox.StandardButton.No:
            delete_autosave()
        else:
            self._deferred_autosave = True

    def _confirm_unsaved_changes(self) -> bool:
        if not self.session or not self.session.is_dirty:
            return True
        answer = QMessageBox.warning(
            self, "저장하지 않은 변경사항",
            "저장하지 않은 변경사항이 있습니다.",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Save:
            return self.save_project()
        if answer == QMessageBox.StandardButton.Discard:
            delete_autosave(); return True
        return False

    def start_other_pdf(self) -> None:
        if not self._confirm_unsaved_changes():
            return
        self.session = None; self.path = None
        self.file_label.setText("선택된 PDF 없음"); self.analyze_button.setEnabled(False)
        self.stack.setCurrentWidget(self.start_page); self._update_window_title()

    def closeEvent(self, event) -> None:
        if not self._confirm_unsaved_changes():
            event.ignore(); return
        if not self._deferred_autosave:
            delete_autosave()
        event.accept()

    def _apply_style(self):
        self.setStyleSheet("""
        QMainWindow,QWidget { background:#F7F8FC; color:#262A40; font-family:'Malgun Gothic'; font-size:13px; }
        #title { font-size:30px; font-weight:800; color:#252943; } #subtitle,#fileLabel { color:#737A91; }
        #dropArea { background:white; border:2px dashed #B7B5FA; border-radius:18px; min-height:280px; }
        QPushButton { background:white; border:1px solid #DADDEA; border-radius:9px; padding:10px 18px; font-weight:600; }
        QPushButton:hover { border-color:PRIMARY; } #primaryButton { background:PRIMARY; color:white; border:none; }
        #sectionTitle { font-size:24px; font-weight:800; } #card { background:white; border:1px solid #E6E7EF; border-radius:14px; padding:8px; }
        QTabWidget::pane { border:1px solid #E2E4EE; background:white; border-radius:10px; }
        QTabBar::tab { padding:11px 18px; } QTabBar::tab:selected { color:PRIMARY; font-weight:700; }
        QTableWidget { background:white; border:0; gridline-color:#ECEEF4; } QHeaderView::section { background:#F0F1F7; padding:8px; border:0; font-weight:700; }
        QLineEdit { background:white; border:1px solid #DADDEA; border-radius:8px; padding:8px; }
        QTextEdit { background:white; border:1px solid #DADDEA; border-radius:8px; padding:8px; }
        QProgressBar { border:0; border-radius:6px; background:#E6E7F0; height:12px; } QProgressBar::chunk { border-radius:6px; background:#625EF5; }
        """.replace("PRIMARY", self.branding.primary_color))


def run_gui() -> int:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_TITLE)
    window = MainWindow(); window.show()
    return app.exec()

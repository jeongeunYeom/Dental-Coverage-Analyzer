from __future__ import annotations

APP_UI_PRIMARY = "#234A75"

COLORS = {
    "app_background": "#F5F7FA",
    "surface": "#FFFFFF",
    "primary": APP_UI_PRIMARY,
    "primary_hover": "#1C3D63",
    "primary_soft": "#EAF2FB",
    "text_primary": "#172033",
    "text_secondary": "#667085",
    "border": "#E4E7EC",
    "success": "#16875D",
    "success_bg": "#EAF7F0",
    "warning": "#D68A00",
    "warning_bg": "#FFF6E5",
    "danger": "#D92D20",
    "danger_bg": "#FEF3F2",
}


def build_stylesheet() -> str:
    return f"""
    QMainWindow, QWidget {{
        background:{COLORS["app_background"]};
        color:{COLORS["text_primary"]};
        font-family:"Segoe UI", "Malgun Gothic", sans-serif;
        font-size:13px;
    }}
    QMenuBar {{
        background:{COLORS["surface"]};
        border-bottom:1px solid {COLORS["border"]};
        padding:2px 8px;
    }}
    QMenuBar::item {{ padding:7px 12px; border-radius:6px; }}
    QMenuBar::item:selected {{ background:{COLORS["primary_soft"]}; color:{COLORS["primary"]}; }}
    QMenu {{
        background:{COLORS["surface"]};
        border:1px solid {COLORS["border"]};
        padding:6px;
    }}
    QMenu::item {{ padding:8px 28px 8px 14px; border-radius:6px; }}
    QMenu::item:selected {{ background:{COLORS["primary_soft"]}; color:{COLORS["text_primary"]}; }}

    #title {{ font-size:30px; font-weight:700; color:{COLORS["text_primary"]}; }}
    #subtitle, #fileLabel, #caption, #helperText {{ color:{COLORS["text_secondary"]}; }}
    #sectionTitle {{ font-size:22px; font-weight:700; color:{COLORS["text_primary"]}; }}
    #panelTitle {{ font-size:16px; font-weight:700; color:{COLORS["text_primary"]}; }}
    #startShell {{ background:transparent; }}
    #fileCard, #headerCard, #commentCard, #sourceMetaCard, #emptyState {{
        background:{COLORS["surface"]};
        border:1px solid {COLORS["border"]};
        border-radius:12px;
    }}
    #dropArea {{
        background:{COLORS["surface"]};
        border:2px dashed #B8C5D6;
        border-radius:14px;
        min-height:260px;
    }}
    #dropArea[dropActive="true"] {{
        background:#F5F9FF;
        border-color:#3B6FA5;
    }}
    #dropTitle {{ font-size:16px; font-weight:700; color:{COLORS["text_primary"]}; }}
    #dropDescription {{ font-size:13px; color:{COLORS["text_secondary"]}; }}

    QPushButton {{
        background:{COLORS["surface"]};
        border:1px solid #D0D5DD;
        border-radius:8px;
        padding:9px 16px;
        min-height:18px;
        font-weight:600;
        color:{COLORS["text_primary"]};
    }}
    QPushButton:hover {{ border-color:{COLORS["primary"]}; background:#F9FBFD; }}
    QPushButton:disabled {{
        background:#F2F4F7;
        border-color:{COLORS["border"]};
        color:#98A2B3;
    }}
    QPushButton#primaryButton, QPushButton[buttonRole="primary"] {{
        background:{COLORS["primary"]};
        color:white;
        border:1px solid {COLORS["primary"]};
    }}
    QPushButton#primaryButton:hover, QPushButton[buttonRole="primary"]:hover {{
        background:{COLORS["primary_hover"]};
        border-color:{COLORS["primary_hover"]};
    }}
    QPushButton#primaryButton:disabled, QPushButton[buttonRole="primary"]:disabled {{
        background:#EAECF0;
        border-color:#EAECF0;
        color:#98A2B3;
    }}
    QPushButton[buttonRole="secondary"] {{
        background:{COLORS["surface"]};
        color:{COLORS["text_primary"]};
    }}
    QPushButton[buttonRole="outlinePrimary"] {{
        background:{COLORS["surface"]};
        color:{COLORS["primary"]};
        border-color:#8FB2D5;
    }}
    QPushButton[buttonRole="ghost"] {{
        background:transparent;
        border-color:transparent;
        color:{COLORS["primary"]};
    }}
    QPushButton[buttonRole="danger"] {{
        background:{COLORS["surface"]};
        border-color:#FDA29B;
        color:{COLORS["danger"]};
    }}
    QPushButton[buttonRole="danger"]:hover {{
        background:{COLORS["danger_bg"]};
        border-color:{COLORS["danger"]};
    }}

    QLineEdit, QTextEdit, QTextBrowser {{
        background:{COLORS["surface"]};
        border:1px solid #D0D5DD;
        border-radius:8px;
        padding:8px;
        selection-background-color:{COLORS["primary_soft"]};
        selection-color:{COLORS["text_primary"]};
    }}
    QLineEdit:focus, QTextEdit:focus {{
        border-color:#3B6FA5;
    }}
    QProgressBar {{
        border:0;
        border-radius:5px;
        background:#EAECF0;
        height:10px;
        text-align:center;
        color:transparent;
    }}
    QProgressBar::chunk {{
        border-radius:5px;
        background:{COLORS["primary"]};
    }}

    QTabWidget::pane {{
        border:1px solid {COLORS["border"]};
        border-radius:10px;
        background:{COLORS["surface"]};
        top:-1px;
    }}
    QTabBar::tab {{
        background:transparent;
        color:{COLORS["text_secondary"]};
        padding:12px 16px;
        border:0;
        border-bottom:2px solid transparent;
    }}
    QTabBar::tab:selected {{
        color:{COLORS["primary"]};
        font-weight:700;
        border-bottom:2px solid {COLORS["primary"]};
    }}
    QTabBar::tab:hover {{ color:{COLORS["primary"]}; }}

    #card {{
        background:{COLORS["surface"]};
        border:1px solid {COLORS["border"]};
        border-radius:12px;
    }}
    QLabel[metricLabel="true"] {{
        color:{COLORS["text_secondary"]};
        font-size:12px;
    }}
    QLabel[metricValue="true"] {{
        color:{COLORS["text_primary"]};
        font-size:17px;
        font-weight:700;
    }}
    QLabel[statusBadge="true"] {{
        border-radius:10px;
        padding:4px 10px;
        font-weight:700;
    }}
    QLabel[statusTone="success"] {{ background:{COLORS["success_bg"]}; color:{COLORS["success"]}; }}
    QLabel[statusTone="warning"] {{ background:{COLORS["warning_bg"]}; color:{COLORS["warning"]}; }}
    QLabel[statusTone="danger"] {{ background:{COLORS["danger_bg"]}; color:{COLORS["danger"]}; }}
    QLabel[statusTone="neutral"] {{ background:#F2F4F7; color:{COLORS["text_secondary"]}; }}

    QTableWidget {{
        background:{COLORS["surface"]};
        alternate-background-color:#FCFCFD;
        border:1px solid {COLORS["border"]};
        border-radius:8px;
        gridline-color:#EAECF0;
        selection-background-color:{COLORS["primary_soft"]};
        selection-color:{COLORS["text_primary"]};
    }}
    QHeaderView::section {{
        background:#F8FAFC;
        color:#475467;
        padding:10px 8px;
        border:0;
        border-bottom:1px solid {COLORS["border"]};
        font-weight:700;
    }}
    QTableCornerButton::section {{
        background:#F8FAFC;
        border:0;
        border-bottom:1px solid {COLORS["border"]};
    }}
    QDialog {{
        background:{COLORS["app_background"]};
    }}
    QGroupBox {{
        background:{COLORS["surface"]};
        border:1px solid {COLORS["border"]};
        border-radius:12px;
        margin-top:14px;
        padding:14px 12px 12px 12px;
        font-weight:700;
    }}
    QGroupBox::title {{
        subcontrol-origin:margin;
        left:12px;
        padding:0 6px;
        color:{COLORS["text_primary"]};
    }}
    #brandPreview {{
        background:{COLORS["surface"]};
        border:1px solid {COLORS["border"]};
        border-radius:12px;
        padding:16px;
    }}
    """

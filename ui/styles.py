DARK_STYLE = """
/* Global Base Typography & Color Reset */
QWidget {
    color: #f8fafc;
    font-family: "Inter", "Segoe UI Variable", "Segoe UI", "Noto Sans", Cantarell, "Ubuntu", sans-serif;
    font-size: 11px;
}

/* Main Window & Core Container */
QWidget#MainContainer {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 12px;
}

/* Header & Title Bar */
QWidget#TitleBar {
    background-color: #1e293b;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid #334155;
}

QLabel#AppTitle {
    color: #38bdf8;
    font-weight: bold;
    font-size: 13px;
}

QPushButton#TitleButton {
    background-color: transparent;
    border: none;
    color: #94a3b8;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 6px;
    border-radius: 4px;
}

QPushButton#TitleButton:hover {
    background-color: #334155;
    color: #f8fafc;
}

QPushButton#CloseButton {
    background-color: transparent;
    border: none;
    color: #94a3b8;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 6px;
    border-radius: 4px;
}

QPushButton#CloseButton:hover {
    background-color: #ef4444;
    color: #ffffff;
}

/* Toolbar & Control Panels */
QWidget#ControlPanel {
    background-color: #1e293b;
    border-bottom: 1px solid #334155;
    padding: 6px;
}

QComboBox {
    background-color: #0f172a;
    color: #e2e8f0;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}

QComboBox:hover {
    border-color: #38bdf8;
}

QComboBox::drop-down {
    border: none;
    width: 16px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #f8fafc;
    selection-background-color: #0284c7;
    border: 1px solid #0284c7;
    border-radius: 6px;
    outline: none;
    padding: 4px;
}

QComboBox QAbstractItemView::item {
    min-height: 24px;
    padding: 4px 8px;
    border-radius: 4px;
}

QComboBox QAbstractItemView::item:hover, QComboBox QAbstractItemView::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}

/* Status Pills & Badges */
QLabel#PrivacyBadgeLocal {
    background-color: #064e3b;
    color: #34d399;
    border: 1px solid #059669;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: bold;
}

QLabel#PrivacyBadgeOnline {
    background-color: #451a03;
    color: #fbbf24;
    border: 1px solid #d97706;
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: bold;
}

/* Chat Stream & ScrollArea */
QScrollArea {
    border: none;
    background-color: transparent;
}

QWidget#ChatStream {
    background-color: #0f172a;
}

/* Chat Message Bubbles */
QWidget#UserBubble {
    background-color: #0c4a6e;
    border-radius: 10px;
    padding: 8px 12px;
}

QWidget#AssistantBubble {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 12px;
}

QLabel#MessageText {
    color: #f8fafc;
    font-size: 13px;
    line-height: 1.4;
}

QWidget#GuideStepCard {
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 6px;
}

QWidget#GuideStepCard QPushButton {
    background-color: #334155;
    color: #bae6fd;
    border: none;
    border-radius: 3px;
    padding: 2px 5px;
    font-size: 9px;
}

QWidget#GuideStepCard QPushButton:hover {
    background-color: #0284c7;
    color: #ffffff;
}

QLabel#MessageMeta {
    color: #94a3b8;
    font-size: 9px;
}

/* Input Area & Action Buttons */
QWidget#InputPanel {
    background-color: #1e293b;
    border-top: 1px solid #334155;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
    padding: 8px;
}

QLineEdit#PromptInput, QPlainTextEdit#PromptInput {
    background-color: #0f172a;
    border: 1px solid #475569;
    border-radius: 8px;
    color: #f8fafc;
    padding: 8px 10px;
    font-size: 11px;
}

QLineEdit#PromptInput:focus, QPlainTextEdit#PromptInput:focus {
    border-color: #38bdf8;
}

QPushButton#ChipButton {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#ChipButton:hover {
    background-color: #0284c7;
    color: #ffffff;
}

QWidget#AdvPanel {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
}

QPushButton#AdvToggleBtn {
    background-color: transparent;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton#AdvToggleBtn:hover {
    background-color: #0369a1;
    color: #ffffff;
}

QPushButton#ActionButton {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton#ActionButton:hover {
    background-color: #0369a1;
}

QPushButton#ActionButton:pressed {
    background-color: #075985;
}

QPushButton#CheckScreenButton {
    background-color: #10b981;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton#CheckScreenButton:hover {
    background-color: #059669;
}

QPushButton#SecondaryButton {
    background-color: #334155;
    color: #e2e8f0;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 11px;
}

QPushButton#SecondaryButton:hover {
    background-color: #475569;
    color: #ffffff;
}

QPushButton#IconButton {
    background-color: #1e293b;
    border: 1px solid #475569;
    color: #38bdf8;
    font-size: 11px;
    font-weight: bold;
    border-radius: 6px;
    padding: 4px 8px;
}

QPushButton#IconButton:hover {
    background-color: #334155;
    color: #7dd3fc;
    border-color: #38bdf8;
}

QPushButton#IconButton:pressed {
    background-color: #0284c7;
    color: #ffffff;
}

/* Scrollbar */
QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 6px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #0f172a;
    height: 6px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal {
    background: #334155;
    border-radius: 3px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background: #475569;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Opacity / Transparency Slider */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #334155;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #38bdf8;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #f8fafc;
    border: 1px solid #0284c7;
    width: 10px;
    height: 10px;
    margin: -3px 0;
    border-radius: 5px;
}

QSlider::handle:horizontal:hover {
    background: #38bdf8;
}
"""

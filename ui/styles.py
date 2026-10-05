DARK_STYLE = """
/* Global Base Typography & Color Reset */
QWidget {
    color: #edece8;
    font-family: "Inter", "Segoe UI Variable", "Segoe UI", "Noto Sans", Cantarell, "Ubuntu", sans-serif;
    font-size: 12px;
}

/* Main Window & Core Container */
QWidget#MainContainer {
    background-color: #191b20;
    border: 1px solid #363a43;
    border-radius: 12px;
}

/* Header & Title Bar */
QWidget#TitleBar {
    background-color: #22252b;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid #363a43;
}

QLabel#AppTitle {
    color: #edece8;
    font-weight: bold;
    font-size: 25px;
}

QFrame#PreviewPanel {
    background-color: #1c1f25;
    border: 1px dashed #454b59;
    border-radius: 8px;
}

QLabel#WorkspaceHeading {
    color: #a2a7b2;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 2px;
    padding: 6px 2px;
}

QPushButton:disabled {
    color: #777e8c;
    background-color: #272b33;
    border-color: #363a43;
}

QPushButton#TitleButton {
    background-color: transparent;
    border: none;
    color: #a2a7b2;
    font-size: 11px;
    font-weight: bold;
    padding: 3px 6px;
    border-radius: 4px;
}

QPushButton#TitleButton:hover {
    background-color: #363a43;
    color: #edece8;
}

QPushButton#CloseButton {
    background-color: transparent;
    border: none;
    color: #a2a7b2;
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
    background-color: #22252b;
    border-bottom: 1px solid #363a43;
    padding: 6px;
}

QComboBox {
    background-color: #191b20;
    color: #d8d9dc;
    border: 1px solid #4c515e;
    border-radius: 6px;
    padding: 4px 8px;
    font-size: 11px;
}

QComboBox:hover {
    border-color: #7293ff;
}

QComboBox::drop-down {
    border: none;
    width: 16px;
}

QComboBox QAbstractItemView {
    background-color: #22252b;
    color: #edece8;
    selection-background-color: #456be3;
    border: 1px solid #456be3;
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
    background-color: #456be3;
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
    background-color: #191b20;
}

/* Chat Message Bubbles */
QWidget#UserBubble {
    background-color: #262e46;
    border-radius: 6px;
    padding: 8px 12px;
}

QWidget#AssistantBubble {
    background-color: #22252b;
    border: 1px solid #363a43;
    border-radius: 6px;
    padding: 8px 12px;
}

QLabel#MessageText {
    color: #edece8;
    font-size: 13px;
    line-height: 1.4;
}

QWidget#GuideStepCard {
    background-color: #191b20;
    border: 1px solid #363a43;
    border-radius: 6px;
}

QWidget#GuideStepCard QPushButton {
    background-color: #363a43;
    color: #bdcaff;
    border: none;
    border-radius: 3px;
    padding: 2px 5px;
    font-size: 9px;
}

QWidget#GuideStepCard QPushButton:hover {
    background-color: #456be3;
    color: #ffffff;
}

QLabel#MessageMeta {
    color: #a2a7b2;
    font-size: 9px;
}

/* Input Area & Action Buttons */
QWidget#InputPanel {
    background-color: #22252b;
    border-top: 1px solid #363a43;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
    padding: 8px;
}

QLineEdit#PromptInput, QPlainTextEdit#PromptInput {
    background-color: #191b20;
    border: 1px solid #4c515e;
    border-radius: 8px;
    color: #edece8;
    padding: 8px 10px;
    font-size: 11px;
}

QLineEdit#PromptInput:focus, QPlainTextEdit#PromptInput:focus {
    border-color: #7293ff;
}

QPushButton#ChipButton {
    background-color: #22252b;
    color: #7293ff;
    border: 1px solid #456be3;
    border-radius: 12px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 500;
}

QPushButton#ChipButton:hover {
    background-color: #456be3;
    color: #ffffff;
}

QWidget#AdvPanel {
    background-color: #22252b;
    border: 1px solid #363a43;
    border-radius: 8px;
    padding: 6px;
}

QPushButton#AdvToggleBtn {
    background-color: transparent;
    color: #7293ff;
    border: 1px solid #456be3;
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton#AdvToggleBtn:hover {
    background-color: #3658c1;
    color: #ffffff;
}

QPushButton#ActionButton {
    background-color: #456be3;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 11px;
    font-weight: bold;
}

QPushButton#ActionButton:hover {
    background-color: #3658c1;
}

QPushButton#ActionButton:pressed {
    background-color: #2e48a0;
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
    background-color: #363a43;
    color: #d8d9dc;
    border: 1px solid #4c515e;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 11px;
}

QPushButton#SecondaryButton:hover {
    background-color: #4c515e;
    color: #ffffff;
}

QPushButton#IconButton {
    background-color: #22252b;
    border: 1px solid #4c515e;
    color: #7293ff;
    font-size: 11px;
    font-weight: bold;
    border-radius: 6px;
    padding: 4px 8px;
}

QPushButton#IconButton:hover {
    background-color: #363a43;
    color: #9baeff;
    border-color: #7293ff;
}

QPushButton#IconButton:pressed {
    background-color: #456be3;
    color: #ffffff;
}

/* Scrollbar */
QScrollBar:vertical {
    border: none;
    background: #191b20;
    width: 6px;
    border-radius: 3px;
}

QScrollBar::handle:vertical {
    background: #363a43;
    border-radius: 3px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #4c515e;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    border: none;
    background: #191b20;
    height: 6px;
    border-radius: 3px;
}

QScrollBar::handle:horizontal {
    background: #363a43;
    border-radius: 3px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background: #4c515e;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Opacity / Transparency Slider */
QSlider::groove:horizontal {
    border: none;
    height: 4px;
    background: #363a43;
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background: #7293ff;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background: #edece8;
    border: 1px solid #456be3;
    width: 10px;
    height: 10px;
    margin: -3px 0;
    border-radius: 5px;
}

QSlider::handle:horizontal:hover {
    background: #7293ff;
}
"""

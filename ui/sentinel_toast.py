from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import Qt, Signal, QTimer
from ui.styles import DARK_STYLE

class SentinelToastWidget(QWidget):
    inspect_clicked = Signal(object)   # Emits CandidateRecord
    mute_clicked = Signal()
    dismiss_clicked = Signal(str)     # Emits fingerprint

    def __init__(self, candidate_record, parent=None):
        super().__init__(parent)
        self.candidate = candidate_record

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setStyleSheet(DARK_STYLE)

        self._init_ui()
        self._position_at_bottom_right()

    def _init_ui(self):
        container = QWidget(self)
        container.setObjectName("ControlPanel")
        container.setStyleSheet(
            "background-color: #0f172a; border: 1px solid #ef4444; border-radius: 8px; padding: 6px;"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        # Header Row
        title_lbl = QLabel(f"🛡️ Watchdog: Potential Error Region (Score: {self.candidate.score})")
        title_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(title_lbl)

        msg_lbl = QLabel(f"Target: {self.candidate.title} — Region ({self.candidate.original_bbox.width()}x{self.candidate.original_bbox.height()})")
        msg_lbl.setStyleSheet("font-size: 10px; color: #94a3b8;")
        layout.addWidget(msg_lbl)

        # Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        inspect_btn = QPushButton("🔍 Inspect with AI")
        inspect_btn.setStyleSheet(
            "background-color: #1e3a8a; color: #60a5fa; border: 1px solid #3b82f6; "
            "border-radius: 4px; font-size: 10px; padding: 4px 8px; font-weight: bold;"
        )
        inspect_btn.clicked.connect(self._on_inspect)

        mute_btn = QPushButton("🔕 Mute 5m")
        mute_btn.setObjectName("SecondaryButton")
        mute_btn.setStyleSheet("font-size: 10px; padding: 4px 6px;")
        mute_btn.clicked.connect(self._on_mute)

        dismiss_btn = QPushButton("❌ Dismiss")
        dismiss_btn.setObjectName("SecondaryButton")
        dismiss_btn.setStyleSheet("font-size: 10px; padding: 4px 6px;")
        dismiss_btn.clicked.connect(self._on_dismiss)

        btn_row.addWidget(inspect_btn)
        btn_row.addWidget(mute_btn)
        btn_row.addWidget(dismiss_btn)

        layout.addLayout(btn_row)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(container)

    def _position_at_bottom_right(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            w, h = 420, 110
            self.resize(w, h)
            self.move(geo.right() - w - 20, geo.bottom() - h - 20)

    def _on_inspect(self):
        self.inspect_clicked.emit(self.candidate)
        self.close()

    def _on_mute(self):
        self.mute_clicked.emit()
        self.close()

    def _on_dismiss(self):
        self.dismiss_clicked.emit(self.candidate.fingerprint)
        self.close()

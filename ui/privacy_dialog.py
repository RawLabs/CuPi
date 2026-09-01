from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont


class OpenRouterPrivacyDialog(QDialog):
    accepted_key = pyqtSignal(str)

    def __init__(self, current_key: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("OpenRouter Privacy Notice")
        self.setFixedWidth(420)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 10px;
            }
            QLabel {
                color: #f8fafc;
            }
            QLineEdit {
                background-color: #1e293b;
                border: 1px solid #475569;
                border-radius: 6px;
                color: #f8fafc;
                padding: 8px;
            }
            QPushButton#AcceptBtn {
                background-color: #d97706;
                color: white;
                font-weight: bold;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton#AcceptBtn:hover {
                background-color: #b45309;
            }
            QPushButton#CancelBtn {
                background-color: #334155;
                color: #e2e8f0;
                border-radius: 6px;
                padding: 8px 14px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        # Header Warning Box
        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #451a03; border: 1px solid #d97706; border-radius: 8px; padding: 10px;")
        header_layout = QVBoxLayout(header_frame)
        
        warn_title = QLabel("⚠️ OPENROUTER ONLINE INFERENCE")
        warn_title.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        warn_title.setStyleSheet("color: #fbbf24;")
        header_layout.addWidget(warn_title)

        warn_desc = QLabel(
            "Screenshots sent through OpenRouter leave this computer "
            "and are processed by the selected online model provider."
        )
        warn_desc.setWordWrap(True)
        warn_desc.setStyleSheet("color: #fef3c7; font-size: 11px;")
        header_layout.addWidget(warn_desc)

        layout.addWidget(header_frame)

        # API Key Section
        key_label = QLabel("OpenRouter API Key:")
        key_label.setStyleSheet("font-size: 11px; font-weight: bold; color: #cbd5e1;")
        layout.addWidget(key_label)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("sk-or-v1-...")
        self.key_input.setText(current_key)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.key_input)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("CancelBtn")
        self.cancel_btn.clicked.connect(self.reject)

        self.accept_btn = QPushButton("Confirm & Connect Online")
        self.accept_btn.setObjectName("AcceptBtn")
        self.accept_btn.clicked.connect(self._on_accept)

        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addWidget(self.accept_btn)
        layout.addLayout(btn_layout)

    def _on_accept(self):
        key = self.key_input.text().strip()
        self.accepted_key.emit(key)
        self.accept()

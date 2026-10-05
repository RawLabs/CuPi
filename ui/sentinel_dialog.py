import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton, QFrame, QApplication
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from ui.styles import DARK_STYLE

class SentinelLogDialog(QDialog):
    def __init__(self, logger, metrics, parent=None):
        super().__init__(parent)
        self.logger = logger
        self.metrics = metrics

        self.setWindowTitle("🛡️ Sentinel Watchdog Evaluation Log")
        self.setMinimumSize(540, 420)
        self.setStyleSheet(DARK_STYLE)

        self._init_ui()
        self.refresh_log()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # 1. Header Title
        title_label = QLabel("🛡️ Sentinel Watchdog Evaluation Log")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #f8fafc;")
        layout.addWidget(title_label)

        # 2. Key Metrics Row
        stats_frame = QFrame()
        stats_frame.setStyleSheet("background-color: #1e293b; border-radius: 6px; padding: 6px;")
        stats_layout = QHBoxLayout(stats_frame)
        stats_layout.setContentsMargins(8, 6, 8, 6)

        avg_ms = self.metrics.average_processing_ms if self.metrics else 0.0
        processed = self.metrics.frames_processed if self.metrics else 0
        dropped = self.metrics.frames_dropped_busy if self.metrics else 0
        candidates = self.logger.candidate_count

        self.lbl_latency = QLabel(f"⏱️ Latency: <b>{avg_ms:.1f} ms</b>")
        self.lbl_processed = QLabel(f"📸 Frames: <b>{processed}</b>")
        self.lbl_dropped = QLabel(f"🚫 Dropped: <b>{dropped}</b>")
        self.lbl_candidates = QLabel(f"🎯 Candidates: <b>{candidates}</b>")

        for lbl in [self.lbl_latency, self.lbl_processed, self.lbl_dropped, self.lbl_candidates]:
            lbl.setStyleSheet("font-size: 11px; color: #cbd5e1;")
            stats_layout.addWidget(lbl)

        layout.addWidget(stats_frame)

        # 3. Log Text View
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color: #0f172a; color: #e2e8f0; font-family: monospace; "
            "font-size: 11px; border: 1px solid #334155; border-radius: 4px; padding: 6px;"
        )
        layout.addWidget(self.log_text, 1)

        # 4. Action Buttons Row
        btn_row = QHBoxLayout()

        copy_btn = QPushButton("📋 Copy Log")
        copy_btn.setObjectName("SecondaryButton")
        copy_btn.clicked.connect(self.copy_log)

        open_btn = QPushButton("📁 Open Log File")
        open_btn.setObjectName("SecondaryButton")
        open_btn.clicked.connect(self.open_log_file)

        clear_btn = QPushButton("🧹 Clear")
        clear_btn.setObjectName("SecondaryButton")
        clear_btn.clicked.connect(self.clear_log)

        close_btn = QPushButton("✖ Close")
        close_btn.setObjectName("SecondaryButton")
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(copy_btn)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def refresh_log(self):
        html_lines = []
        for entry in self.logger.event_history:
            ts = entry["timestamp"]
            st = entry["state"]
            msg = entry["message"]
            ms = entry["elapsed_ms"]

            if st == "CANDIDATE":
                color = "#f43f5e"  # Red/rose
            elif st == "OBSERVING":
                color = "#fbbf24"  # Gold
            elif st == "MOTION":
                color = "#c084fc"  # Purple
            else:
                color = "#38bdf8"  # Blue

            line = f'<span style="color: #64748b;">[{ts}]</span> <b style="color: {color};">[{st:<9}]</b> {msg} <span style="color: #64748b;">({ms:.1f}ms)</span>'
            html_lines.append(line)

        if not html_lines:
            html_lines = ['<span style="color: #64748b;">No Sentinel events recorded yet. Activate Watchdog to observe screen changes.</span>']

        self.log_text.setHtml("<br>".join(html_lines))
        self.log_text.moveCursor(self.log_text.textCursor().MoveOperation.End)

    def copy_log(self):
        plain_text = self.log_text.toPlainText()
        QApplication.clipboard().setText(plain_text)

    def open_log_file(self):
        if self.logger.log_path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.logger.log_path.resolve())))

    def clear_log(self):
        self.logger.clear()
        self.refresh_log()

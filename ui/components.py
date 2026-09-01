import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, QSizePolicy, QPlainTextEdit
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage, QIcon, QFont, QKeyEvent

class ChatMessageWidget(QWidget):
    export_requested = pyqtSignal(str, list, str)

    def __init__(self, role: str, text: str, pixmap: QPixmap = None, pixmaps: list = None, guide_type: str = "", production_mode: bool = False, parent=None):
        super().__init__(parent)
        self.text = text
        self.guide_type = guide_type
        self.production_mode = production_mode
        self.pixmaps = list(pixmaps) if pixmaps else ([pixmap] if (pixmap and not pixmap.isNull()) else [])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        is_user = (role == "user")
        
        bubble = QWidget()
        bubble.setObjectName("UserBubble" if is_user else "AssistantBubble")
        bubble_layout = QVBoxLayout(bubble)
        bubble_layout.setContentsMargins(10, 8, 10, 8)
        bubble_layout.setSpacing(6)

        # Header role / timestamp
        meta_layout = QHBoxLayout()
        role_label = QLabel("YOU" if is_user else ("PRODUCTION" if production_mode else "COMPANION"))
        role_label.setObjectName("MessageMeta")
        role_label.setStyleSheet("font-weight: bold; color: " + ("#e0f2fe;" if is_user else "#38bdf8;"))
        
        time_str = time.strftime("%H:%M")
        time_label = QLabel(time_str)
        time_label.setObjectName("MessageMeta")

        meta_layout.addWidget(role_label)
        meta_layout.addStretch()

        if production_mode:
            export_btn = QPushButton("📄 Export Guide")
            export_btn.setObjectName("TitleButton")
            export_btn.setStyleSheet("font-size: 10px; color: #38bdf8; font-weight: bold; padding: 1px 4px;")
            export_btn.setToolTip("Export this drafted guide with its captured steps (.md & .html)")
            export_btn.clicked.connect(lambda: self.export_requested.emit(self.text, self.pixmaps, self.guide_type))
            meta_layout.addWidget(export_btn)

        meta_layout.addWidget(time_label)
        bubble_layout.addLayout(meta_layout)

        # Multiple Screenshot thumbnails preview if present
        all_pixmaps = self.pixmaps
        if all_pixmaps:
            img_container = QWidget()
            img_layout = QVBoxLayout(img_container)
            img_layout.setContentsMargins(0, 0, 0, 0)
            img_layout.setSpacing(4)

            count_str = f"📷 {len(all_pixmaps)} Screenshot{'s' if len(all_pixmaps) > 1 else ''} Attached"
            badge_label = QLabel(count_str)
            badge_label.setStyleSheet("color: #38bdf8; font-size: 10px; font-weight: bold;")
            img_layout.addWidget(badge_label)

            thumbs_row = QWidget()
            thumbs_layout = QHBoxLayout(thumbs_row)
            thumbs_layout.setContentsMargins(0, 0, 0, 0)
            thumbs_layout.setSpacing(6)

            for p in all_pixmaps:
                if p and not p.isNull():
                    thumb_label = QLabel()
                    scaled_pix = p.scaled(130, 85, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    thumb_label.setPixmap(scaled_pix)
                    thumb_label.setStyleSheet("border: 1px solid #0284c7; border-radius: 4px;")
                    thumbs_layout.addWidget(thumb_label)
            thumbs_layout.addStretch()
            img_layout.addWidget(thumbs_row)

            bubble_layout.addWidget(img_container)

        # Body text
        text_label = QLabel()
        text_label.setObjectName("MessageText")
        # Assistant responses are Markdown.  QLabel otherwise treats the source
        # literally, exposing markers such as **bold**, ### headings and `code`.
        text_label.setTextFormat(Qt.TextFormat.MarkdownText)
        text_label.setText(text)
        text_label.setWordWrap(True)
        text_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse |
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        text_label.setOpenExternalLinks(True)
        bubble_layout.addWidget(text_label)

        # Outer layout positioning
        outer_layout = QHBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        if is_user:
            outer_layout.addStretch(1)
            outer_layout.addWidget(bubble, 4)
        else:
            outer_layout.addWidget(bubble, 4)
            outer_layout.addStretch(1)

        layout.addLayout(outer_layout)


class AttachedImageBadge(QWidget):
    edit_requested = pyqtSignal(int)
    remove_requested = pyqtSignal(int)

    def __init__(self, pixmaps: list, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        self.setStyleSheet("""
            QWidget {
                background-color: #1e293b;
                border: 1px solid #0284c7;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 2px 8px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0369a1;
            }
        """)

        count = len(pixmaps) if pixmaps else 0
        header = QHBoxLayout()
        lbl = QLabel("📷 Current snapshot" if count == 1 else f"📷 {count} snapshots")
        lbl.setStyleSheet("color: #7dd3fc; font-size: 11px; font-weight: bold;")
        hint = QLabel("Edit or replace before asking AI")
        hint.setStyleSheet("color: #94a3b8; font-size: 10px;")
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(hint)
        layout.addLayout(header)

        steps = QHBoxLayout()
        steps.setSpacing(6)
        for index, pixmap in enumerate(pixmaps or []):
            if not pixmap or pixmap.isNull():
                continue
            card = QWidget()
            card.setObjectName("GuideStepCard")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 5, 5, 4)
            card_layout.setSpacing(3)
            thumb = QLabel()
            thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            thumb.setPixmap(pixmap.scaled(78, 52, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            thumb.setStyleSheet("border-radius: 3px; border: 1px solid #0369a1;")
            step_label = QLabel(f"Step {index + 1}")
            step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_label.setStyleSheet("color: #cbd5e1; font-size: 10px; font-weight: bold;")
            actions = QHBoxLayout()
            actions.setSpacing(3)
            edit_btn = QPushButton("Edit")
            edit_btn.setToolTip(f"Edit annotations for Step {index + 1}")
            edit_btn.clicked.connect(lambda _=False, i=index: self.edit_requested.emit(i))
            remove_btn = QPushButton("×")
            remove_btn.setToolTip(f"Remove Step {index + 1}")
            remove_btn.clicked.connect(lambda _=False, i=index: self.remove_requested.emit(i))
            actions.addWidget(edit_btn)
            actions.addWidget(remove_btn)
            card_layout.addWidget(thumb)
            card_layout.addWidget(step_label)
            card_layout.addLayout(actions)
            steps.addWidget(card)
        steps.addStretch()
        layout.addLayout(steps)


class PromptTextEdit(QPlainTextEdit):
    return_pressed = pyqtSignal()
    escape_pressed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(80)
        self.setMinimumHeight(38)

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.return_pressed.emit()
                event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            if self.toPlainText():
                self.clear()
            self.escape_pressed.emit()
            event.accept()
        else:
            super().keyPressEvent(event)

    def text(self) -> str:
        return self.toPlainText()

    def setText(self, text: str):
        self.setPlainText(text)

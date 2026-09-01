import math
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QButtonGroup, QRadioButton
)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QMouseEvent
from PyQt6.QtCore import Qt, QPoint, QRect
from capture.annotation_utils import draw_annotation_on_pixmap


class InteractiveAnnotationCanvas(QLabel):
    def __init__(self, original_pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.original_pixmap = original_pixmap
        self.current_shape = "box"
        self.annotations = []  # list of dicts: {'type': shape, 'coords': [...] }
        self.drag_start = None
        self.drag_end = None
        self.is_dragging = False

        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.update_display()

    def set_shape(self, shape_name: str):
        self.current_shape = shape_name.lower()

    def clear_annotations(self):
        self.annotations.clear()
        self.update_display()

    def get_annotated_pixmap(self) -> QPixmap:
        result = self.original_pixmap.copy()
        for ann in self.annotations:
            result = draw_annotation_on_pixmap(result, ann["type"], ann["coords"])
        return result

    def update_display(self):
        if self.original_pixmap.isNull():
            return
        annotated = self.get_annotated_pixmap()
        target_w = max(400, self.width())
        target_h = max(300, self.height())
        scaled = annotated.scaled(
            target_w, target_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_display()

    def _window_to_image_coords(self, pos: QPoint) -> tuple:
        if not self.pixmap() or self.original_pixmap.isNull():
            return 0, 0

        pix_w = self.pixmap().width()
        pix_h = self.pixmap().height()
        lbl_w = self.width()
        lbl_h = self.height()

        # Offset due to AlignmentFlag.AlignCenter
        offset_x = (lbl_w - pix_w) / 2.0
        offset_y = (lbl_h - pix_h) / 2.0

        rel_x = pos.x() - offset_x
        rel_y = pos.y() - offset_y

        scale_x = self.original_pixmap.width() / float(pix_w) if pix_w > 0 else 1.0
        scale_y = self.original_pixmap.height() / float(pix_h) if pix_h > 0 else 1.0

        img_x = int(rel_x * scale_x)
        img_y = int(rel_y * scale_y)

        img_x = max(0, min(img_x, self.original_pixmap.width()))
        img_y = max(0, min(img_y, self.original_pixmap.height()))

        return img_x, img_y

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            img_x, img_y = self._window_to_image_coords(event.pos())
            self.drag_start = (img_x, img_y)
            self.is_dragging = True

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.is_dragging:
            self.is_dragging = False
            img_x, img_y = self._window_to_image_coords(event.pos())
            self.drag_end = (img_x, img_y)

            start_x, start_y = self.drag_start if self.drag_start else (img_x, img_y)
            dist = math.hypot(img_x - start_x, img_y - start_y)

            if dist > 15:
                if self.current_shape in ("box", "circle"):
                    x1, y1 = min(start_x, img_x), min(start_y, img_y)
                    x2, y2 = max(start_x, img_x), max(start_y, img_y)
                    self.annotations.append({"type": self.current_shape, "coords": [x1, y1, x2, y2]})
                elif self.current_shape == "arrow":
                    self.annotations.append({"type": "arrow", "coords": [img_x, img_y, start_x, start_y]})
                else:
                    self.annotations.append({"type": self.current_shape, "coords": [img_x, img_y]})
            else:
                # Single click
                self.annotations.append({"type": self.current_shape, "coords": [img_x, img_y]})

            self.update_display()


class AnnotationDialog(QDialog):
    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("✏️ Annotate Screenshot")
        self.setMinimumSize(900, 700)

        self.setStyleSheet("""
            QDialog {
                background-color: #0f172a;
                color: #f8fafc;
            }
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                border: 1px solid #0284c7;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0284c7;
                color: #ffffff;
            }
            QRadioButton {
                color: #e2e8f0;
                font-weight: bold;
                font-size: 13px;
                spacing: 6px;
            }
        """)

        layout = QVBoxLayout(self)

        # Header toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(16)

        title_lbl = QLabel("Select Tool:")
        title_lbl.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")
        toolbar.addWidget(title_lbl)

        self.button_group = QButtonGroup(self)

        self.rb_box = QRadioButton("🟥 Box (Outline)")
        self.rb_box.setChecked(True)
        self.rb_circle = QRadioButton("🔴 Circle")
        self.rb_crosshair = QRadioButton("🎯 Crosshair")
        self.rb_arrow = QRadioButton("🏹 Arrow")

        self.button_group.addButton(self.rb_box)
        self.button_group.addButton(self.rb_circle)
        self.button_group.addButton(self.rb_crosshair)
        self.button_group.addButton(self.rb_arrow)

        toolbar.addWidget(self.rb_box)
        toolbar.addWidget(self.rb_circle)
        toolbar.addWidget(self.rb_crosshair)
        toolbar.addWidget(self.rb_arrow)

        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(self._clear_canvas)
        toolbar.addWidget(clear_btn)

        layout.addLayout(toolbar)

        # Instructions hint label
        hint_lbl = QLabel("💡 Tip: Drag across a button to draw a Box/Circle, or click to place a shape.")
        hint_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(hint_lbl)

        # Interactive Canvas
        self.canvas = InteractiveAnnotationCanvas(pixmap, self)
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.canvas, 1)

        # Connect radio buttons
        self.rb_box.toggled.connect(lambda: self.canvas.set_shape("box"))
        self.rb_circle.toggled.connect(lambda: self.canvas.set_shape("circle"))
        self.rb_crosshair.toggled.connect(lambda: self.canvas.set_shape("crosshair"))
        self.rb_arrow.toggled.connect(lambda: self.canvas.set_shape("arrow"))

        # Bottom Actions
        actions = QHBoxLayout()
        actions.addStretch(1)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        actions.addWidget(cancel_btn)

        save_btn = QPushButton("Save & Apply Annotation")
        save_btn.setStyleSheet("background-color: #0284c7; color: white;")
        save_btn.clicked.connect(self.accept)
        actions.addWidget(save_btn)

        layout.addLayout(actions)

    def _clear_canvas(self):
        self.canvas.clear_annotations()

    def get_result_pixmap(self) -> QPixmap:
        return self.canvas.get_annotated_pixmap()

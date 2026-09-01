from PyQt6.QtWidgets import QWidget, QRubberBand, QApplication
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QCursor, QGuiApplication, QPixmap
from capture.screen_capture import SourceTarget


class PickerOverlay(QWidget):
    target_selected = pyqtSignal(SourceTarget)
    canceled = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.BypassWindowManagerHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.origin = QPoint()
        self.rubber_band: QRubberBand = None
        self.is_selecting = False

        # Cover virtual geometry of all screens
        geo = QRect()
        for scr in QGuiApplication.screens():
            geo = geo.united(scr.geometry())
        self.setGeometry(geo)

    def show_overlay(self):
        self.origin = QPoint()
        self.is_selecting = False
        self.setGeometry(self._get_total_screen_rect())
        self.show()
        self.raise_()
        self.activateWindow()

    def _get_total_screen_rect(self) -> QRect:
        total = QRect()
        for scr in QGuiApplication.screens():
            total = total.united(scr.geometry())
        return total

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 80))
        
        # Banner instruction box
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(15, 23, 42, 220)) # Dark slate
        box_w, box_h = 440, 50
        box_x = (self.width() - box_w) // 2
        box_y = 60
        painter.drawRoundedRect(box_x, box_y, box_w, box_h, 10, 10)

        painter.setPen(QPen(QColor(255, 255, 255), 1))
        font = painter.font()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRect(box_x, box_y, box_w, box_h),
            Qt.AlignmentFlag.AlignCenter,
            "📐 Click & Drag to Select Screen Area (ESC to cancel)"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.pos()
            if not self.rubber_band:
                self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
            self.rubber_band.setGeometry(QRect(self.origin, self.origin))
            self.rubber_band.show()
            self.is_selecting = True

    def mouseMoveEvent(self, event):
        if self.is_selecting and self.rubber_band:
            self.rubber_band.setGeometry(QRect(self.origin, event.pos()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            if self.rubber_band:
                rect = self.rubber_band.geometry()
                self.rubber_band.hide()
                self.close()

                if rect.width() > 20 and rect.height() > 20:
                    target = SourceTarget(
                        target_type="region",
                        target_id="custom_region",
                        name=f"Selected Area ({rect.width()}x{rect.height()})",
                        rect=rect
                    )
                    self.target_selected.emit(target)
                else:
                    # Single click - select default screen target
                    target = SourceTarget(
                        target_type="screen",
                        target_id="screen_0",
                        name="Full Screen"
                    )
                    self.target_selected.emit(target)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.rubber_band:
                self.rubber_band.hide()
            self.close()
            self.canceled.emit()

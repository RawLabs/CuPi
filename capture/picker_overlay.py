import re
import shutil

from PyQt6.QtWidgets import QWidget, QRubberBand
from PyQt6.QtCore import Qt, QPoint, QRect, pyqtSignal, QProcess
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
            Qt.WindowType.Window
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.origin = QPoint()
        self.rubber_band: QRubberBand = None
        self.is_selecting = False
        self._picker_process: QProcess | None = None

        self._screen_geometry = QRect()

    def show_overlay(self):
        # On wlroots compositors (including Hyprland), slurp uses the native
        # layer-shell selection surface.  It can receive input across the
        # desktop without making this application's window fullscreen or
        # changing focus/workspaces.
        if shutil.which("slurp"):
            self._show_native_picker()
            return

        self.origin = QPoint()
        self.is_selecting = False
        # Wayland compositors do not honor a top-level widget that tries to
        # span the virtual desktop, and BypassWindowManagerHint can leave its
        # input surface constrained to a small area.  Fullscreen the overlay
        # on the screen under the pointer instead.
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._screen_geometry = screen.geometry() if screen else self._get_total_screen_rect()
        self.setGeometry(self._screen_geometry)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()

    def _show_native_picker(self) -> None:
        self._picker_process = QProcess(self)
        self._picker_process.finished.connect(self._on_native_picker_finished)
        self._picker_process.start("slurp", ["-f", "%x,%y %wx%h"])

    @staticmethod
    def _parse_native_geometry(output: str) -> QRect | None:
        match = re.fullmatch(r"\s*(-?\d+),(-?\d+)\s+(\d+)x(\d+)\s*", output)
        if not match:
            return None
        x, y, width, height = (int(value) for value in match.groups())
        return QRect(x, y, width, height)

    def _on_native_picker_finished(self, exit_code: int, _exit_status) -> None:
        process = self._picker_process
        self._picker_process = None
        output = bytes(process.readAllStandardOutput()).decode(errors="replace") if process else ""
        if process:
            process.deleteLater()

        rect = self._parse_native_geometry(output) if exit_code == 0 else None
        if rect and rect.width() > 20 and rect.height() > 20:
            self.target_selected.emit(SourceTarget(
                target_type="region",
                target_id="custom_region",
                name=f"Selected Area ({rect.width()}x{rect.height()})",
                rect=rect,
            ))
        else:
            # Escape is reported by slurp as a non-zero exit and should only
            # dismiss the picker, never close the companion application.
            self.canceled.emit()

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
                    # QRubberBand geometry is local to this fullscreen widget;
                    # screen capture backends require global desktop geometry.
                    target = SourceTarget(
                        target_type="region",
                        target_id="custom_region",
                        name=f"Selected Area ({rect.width()}x{rect.height()})",
                        rect=rect.translated(self._screen_geometry.topLeft())
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

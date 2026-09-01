import math
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QBrush, QPolygonF
from PyQt6.QtCore import Qt, QRect, QPointF

def draw_annotation_on_pixmap(pixmap: QPixmap, annotation_type: str, coords: list, is_normalized: bool = False) -> QPixmap:
    """
    Draws an annotation (circle, box, crosshair, or arrow) on a copy of the pixmap.
    No dark fill on boxes/circles — text underneath stays 100% crisp and readable.
    Sizing and stroke widths are dynamically scaled to image dimensions.
    """
    if pixmap.isNull():
        return pixmap

    annotated_pixmap = pixmap.copy()
    painter = QPainter(annotated_pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    img_w = pixmap.width()
    img_h = pixmap.height()

    def norm_x(val):
        v = float(val)
        if 0.0 < v <= 1.0:
            return v * img_w
        if 1.0 < v <= img_w:
            return v
        if is_normalized and 1.0 < v <= 1000.0:
            return (v / 1000.0) * img_w
        return v

    def norm_y(val):
        v = float(val)
        if 0.0 < v <= 1.0:
            return v * img_h
        if 1.0 < v <= img_h:
            return v
        if is_normalized and 1.0 < v <= 1000.0:
            return (v / 1000.0) * img_h
        return v

    if not coords or len(coords) < 2:
        painter.end()
        return annotated_pixmap

    # Dynamic line stroke and shape size relative to image resolution
    base_dim = max(img_w, img_h)
    pen_width = max(3, int(base_dim * 0.003))     # e.g., ~8px stroke on 2800px image
    shape_size = max(36, int(base_dim * 0.035))   # e.g., ~100px shape on 2800px image

    pen = QPen(QColor(255, 30, 30))
    pen.setWidth(pen_width)
    painter.setPen(pen)

    shape_type = (annotation_type or "box").lower()

    # 1. Handle Bounding Box / Dragged Region [x1, y1, x2, y2]
    if len(coords) >= 4 and shape_type in ("box", "circle"):
        x1, y1 = int(norm_x(coords[0])), int(norm_y(coords[1]))
        x2, y2 = int(norm_x(coords[2])), int(norm_y(coords[3]))
        rx, ry = min(x1, x2), min(y1, y2)
        rw, rh = abs(x2 - x1), abs(y2 - y1)

        if shape_type == "box":
            # Clean hollow red border with rounded corners (NO dark red fill!)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rx, ry, rw, rh, 6, 6)
        elif shape_type == "circle":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(rx, ry, rw, rh)

        painter.end()
        return annotated_pixmap

    # 2. Point-based annotations [x, y]
    x, y = int(norm_x(coords[0])), int(norm_y(coords[1]))
    r = shape_size // 2

    if shape_type == "box":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x - r, y - r, shape_size, shape_size, 4, 4)
    elif shape_type == "circle":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(x - r, y - r, shape_size, shape_size)
    elif shape_type == "crosshair":
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(x - shape_size, y, x + shape_size, y)
        painter.drawLine(x, y - shape_size, x, y + shape_size)
        painter.drawEllipse(x - r, y - r, shape_size, shape_size)
    elif shape_type == "arrow":
        if len(coords) >= 4:
            tail_x, tail_y = int(norm_x(coords[0])), int(norm_y(coords[1]))
            x, y = int(norm_x(coords[2])), int(norm_y(coords[3]))
        else:
            tail_x = x - shape_size * 1.5 if x >= shape_size * 1.5 else x + shape_size * 1.5
            tail_y = y - shape_size * 1.5 if y >= shape_size * 1.5 else y + shape_size * 1.5

        # Shaft
        painter.drawLine(int(tail_x), int(tail_y), x, y)

        # Arrowhead tip
        angle = math.atan2(y - tail_y, x - tail_x)
        arrow_len = max(18, int(shape_size * 0.45))
        wing1_angle = angle + math.pi - (math.pi / 6)
        wing2_angle = angle + math.pi + (math.pi / 6)

        p1_x = x + arrow_len * math.cos(wing1_angle)
        p1_y = y + arrow_len * math.sin(wing1_angle)
        p2_x = x + arrow_len * math.cos(wing2_angle)
        p2_y = y + arrow_len * math.sin(wing2_angle)

        arrowhead = QPolygonF([
            QPointF(float(x), float(y)),
            QPointF(float(p1_x), float(p1_y)),
            QPointF(float(p2_x), float(p2_y))
        ])
        painter.setBrush(QBrush(QColor(255, 30, 30)))
        painter.drawPolygon(arrowhead)
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(x - r, y - r, shape_size, shape_size, 4, 4)

    painter.end()
    return annotated_pixmap

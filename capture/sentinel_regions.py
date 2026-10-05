import numpy as np
from PySide6.QtCore import QRect
from typing import Optional, List, Tuple

def compute_iou(rect1: QRect, rect2: QRect) -> float:
    """Computes Intersection-over-Union (IoU) ratio between two QRects."""
    inter = rect1.intersected(rect2)
    if inter.isEmpty():
        return 0.0
    inter_area = float(inter.width() * inter.height())
    area1 = float(rect1.width() * rect1.height())
    area2 = float(rect2.width() * rect2.height())
    union_area = area1 + area2 - inter_area
    if union_area <= 0:
        return 0.0
    return inter_area / union_area

def extract_candidate_regions(
    changed_mask: np.ndarray,
    min_area: int = 80,
    max_screen_ratio: float = 0.65
) -> List[Tuple[int, int, int, int]]:
    """
    Extracts cleaned bounding boxes (x, y, w, h) from downsampled 2D boolean mask.
    Filters tiny isolated components and extracts overall bounding boxes.
    """
    if not np.any(changed_mask):
        return []

    height, width = changed_mask.shape
    total_area = height * width

    # Find non-zero indices
    y_indices, x_indices = np.where(changed_mask)
    if len(y_indices) < min_area:
        return []

    min_x, max_x = int(np.min(x_indices)), int(np.max(x_indices))
    min_y, max_y = int(np.min(y_indices)), int(np.max(y_indices))

    w = max_x - min_x + 1
    h = max_y - min_y + 1
    bbox_area = w * h

    if w < 10 or h < 8:
        return []

    return [(min_x, min_y, w, h)]

def scale_and_clamp_bbox(
    bbox: Tuple[int, int, int, int],
    analyzed_size: Tuple[int, int],
    original_size: Tuple[int, int],
    padding: int = 20
) -> QRect:
    """
    Scales bounding box from downsampled coordinates to original image coordinates
    with padding and corner clamping.
    """
    x, y, w, h = bbox
    analyzed_w, analyzed_h = analyzed_size
    orig_w, orig_h = original_size

    if analyzed_w <= 0 or analyzed_h <= 0 or orig_w <= 0 or orig_h <= 0:
        return QRect(0, 0, 0, 0)

    scale_x = float(orig_w) / float(analyzed_w)
    scale_y = float(orig_h) / float(analyzed_h)

    # Calculate padded corners on scaled dimensions
    x1 = max(0, int(round((x - padding) * scale_x)))
    y1 = max(0, int(round((y - padding) * scale_y)))
    x2 = min(orig_w, int(round((x + w + padding) * scale_x)))
    y2 = min(orig_h, int(round((y + h + padding) * scale_y)))

    rect_w = max(0, x2 - x1)
    rect_h = max(0, y2 - y1)

    return QRect(x1, y1, rect_w, rect_h)

import numpy as np
from dataclasses import dataclass
from typing import Tuple, Dict, Any

@dataclass(frozen=True)
class VisualSignalResult:
    has_new_red: bool
    has_text_like_edges: bool
    has_dialog_geometry: bool
    is_large_region: bool
    composite_score: int

class SentinelSignalEvaluator:
    """
    Evaluates visual signals (red accents, edge density, dialog bounds) on NumPy regions.
    Computes a composite anomaly score (threshold S >= 4 for Toast display).
    """
    def evaluate_signals(
        self,
        curr_np: np.ndarray,
        base_np: np.ndarray,
        bbox: Tuple[int, int, int, int],
        is_persistent: bool,
        is_scene_change: bool,
        is_sustained_motion: bool
    ) -> VisualSignalResult:
        if curr_np is None or base_np is None or bbox is None:
            return VisualSignalResult(
                has_new_red=False,
                has_text_like_edges=False,
                has_dialog_geometry=False,
                is_large_region=False,
                composite_score=0
            )

        x, y, w, h = bbox
        img_h, img_w, _ = curr_np.shape

        # Crop region safely
        curr_crop = curr_np[y:y+h, x:x+w]
        base_crop = base_np[y:y+h, x:x+w] if base_np.shape == curr_np.shape else None

        if curr_crop.size == 0:
            return VisualSignalResult(
                has_new_red=False,
                has_text_like_edges=False,
                has_dialog_geometry=False,
                is_large_region=False,
                composite_score=0
            )

        # 1. New Red Accent Check (R > 170, G < 70, B < 70)
        curr_red_mask = (curr_crop[:, :, 0] > 170) & (curr_crop[:, :, 1] < 70) & (curr_crop[:, :, 2] < 70)
        curr_red_pixels = np.count_nonzero(curr_red_mask)

        if base_crop is not None:
            base_red_mask = (base_crop[:, :, 0] > 170) & (base_crop[:, :, 1] < 70) & (base_crop[:, :, 2] < 70)
            new_red_pixels = np.count_nonzero(curr_red_mask & ~base_red_mask)
        else:
            new_red_pixels = curr_red_pixels

        has_new_red = (new_red_pixels > max(15, int(curr_crop.shape[0] * curr_crop.shape[1] * 0.005)))

        # 2. Text-Like Edge Density Check (high frequency luminance gradient)
        gray = (0.299 * curr_crop[:, :, 0] + 0.587 * curr_crop[:, :, 1] + 0.114 * curr_crop[:, :, 2]).astype(np.int16)
        if gray.shape[0] > 2 and gray.shape[1] > 2:
            dx = np.abs(gray[:, 1:] - gray[:, :-1])
            dy = np.abs(gray[1:, :] - gray[:-1, :])
            edge_ratio = (np.count_nonzero(dx > 25) + np.count_nonzero(dy > 25)) / float(gray.size)
            has_text_like_edges = (edge_ratio >= 0.08)
        else:
            has_text_like_edges = False

        # 3. Dialog Geometry Check (occupying 5% - 50% of display with rectangular shape)
        region_ratio = float(w * h) / float(img_w * img_h)
        is_large_region = (region_ratio > 0.65)
        has_dialog_geometry = (0.05 <= region_ratio <= 0.55) and (w > 120 and h > 80)

        # 4. Composite Scoring
        score = 0
        if is_persistent:
            score += 3
        if has_new_red:
            score += 2
        if has_text_like_edges:
            score += 1
        if has_dialog_geometry:
            score += 1

        if is_scene_change:
            score -= 4
        if is_sustained_motion:
            score -= 3

        return VisualSignalResult(
            has_new_red=has_new_red,
            has_text_like_edges=has_text_like_edges,
            has_dialog_geometry=has_dialog_geometry,
            is_large_region=is_large_region,
            composite_score=score
        )

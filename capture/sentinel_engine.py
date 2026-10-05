import time
import numpy as np
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Tuple, List
from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QImage

from capture.sentinel_regions import extract_candidate_regions, scale_and_clamp_bbox
from capture.sentinel_signals import SentinelSignalEvaluator, VisualSignalResult

class SentinelState(Enum):
    PAUSED = auto()
    STABLE = auto()
    MOTION = auto()
    OBSERVING = auto()
    CANDIDATE = auto()

@dataclass
class SentinelMetrics:
    frames_captured: int = 0
    frames_processed: int = 0
    frames_dropped_busy: int = 0
    average_processing_ms: float = 0.0

@dataclass(frozen=True)
class SentinelResult:
    state: SentinelState
    frame_delta_ratio: float
    baseline_delta_ratio: float
    stable_duration_sec: float
    message: str
    original_bbox: Optional[QRect] = None
    crop_image: Optional[QImage] = None
    signals: Optional[VisualSignalResult] = None

class SentinelEngine:
    """
    Lightweight, channel-correct frame differencing and state classifier.
    Features dual-threshold motion hysteresis, downsampled mask cleanup,
    padded coordinate scaling, and composite signal scoring.
    """
    def __init__(
        self,
        motion_enter_threshold: float = 0.004,
        motion_exit_threshold: float = 0.0015,
        full_scene_threshold: float = 0.35,
        stable_duration_sec: float = 3.0,
        observation_duration_sec: float = 3.0,
        motion_hits_threshold: int = 2,
        motion_threshold: Optional[float] = None
    ):
        if motion_threshold is not None:
            motion_enter_threshold = motion_threshold

        self.motion_enter_threshold = motion_enter_threshold
        self.motion_exit_threshold = motion_exit_threshold
        self.full_scene_threshold = full_scene_threshold
        self.stable_duration_sec = stable_duration_sec
        self.observation_duration_sec = observation_duration_sec
        self.motion_hits_threshold = motion_hits_threshold

        self.prev_np: Optional[np.ndarray] = None
        self.stable_baseline_np: Optional[np.ndarray] = None

        self.last_motion_time: float = time.monotonic()
        self.observing_start_time: Optional[float] = None
        self.motion_consecutive_hits: int = 0
        self.state: SentinelState = SentinelState.STABLE
        self.signal_evaluator = SentinelSignalEvaluator()

    def qimage_to_numpy(self, qimage: QImage, max_dim: int = 480) -> np.ndarray:
        """Converts QImage to downsampled RGB numpy array."""
        if qimage.isNull():
            return np.zeros((1, 1, 3), dtype=np.uint8)

        w, h = qimage.width(), qimage.height()
        if w > max_dim or h > max_dim:
            qimage = qimage.scaled(
                max_dim, max_dim,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation
            )

        img = qimage.convertToFormat(QImage.Format.Format_RGB888)
        width, height = img.width(), img.height()
        # Qt pads scanlines to four bytes; copy before the temporary QImage dies.
        rows = np.frombuffer(img.constBits(), dtype=np.uint8).reshape(height, img.bytesPerLine())
        return rows[:, :width * 3].reshape(height, width, 3).copy()

    def reset_baselines(self):
        """Resets baseline states."""
        self.prev_np = None
        self.stable_baseline_np = None
        self.last_motion_time = time.monotonic()
        self.observing_start_time = None
        self.motion_consecutive_hits = 0
        self.state = SentinelState.STABLE

    def process_frame(self, qimage: QImage, timestamp: float = 0.0) -> SentinelResult:
        now = time.monotonic() if timestamp == 0.0 else timestamp
        curr_np = self.qimage_to_numpy(qimage)
        orig_w, orig_h = qimage.width(), qimage.height()

        # First frame initialization
        if self.prev_np is None or self.prev_np.shape != curr_np.shape:
            self.prev_np = curr_np
            self.stable_baseline_np = curr_np
            self.last_motion_time = now
            self.state = SentinelState.STABLE
            return SentinelResult(
                state=SentinelState.STABLE,
                frame_delta_ratio=0.0,
                baseline_delta_ratio=0.0,
                stable_duration_sec=0.0,
                message="Initialized baselines"
            )

        # 1. Channel-correct Frame Delta (vs previous frame)
        diff_prev = np.abs(curr_np.astype(np.int16) - self.prev_np.astype(np.int16))
        changed_mask_prev = np.any(diff_prev > 30, axis=2)
        frame_delta_ratio = float(np.count_nonzero(changed_mask_prev)) / float(changed_mask_prev.size)

        # 2. Channel-correct Baseline Delta (vs stable baseline)
        diff_base = np.abs(curr_np.astype(np.int16) - self.stable_baseline_np.astype(np.int16))
        changed_mask_base = np.any(diff_base > 30, axis=2)
        baseline_delta_ratio = float(np.count_nonzero(changed_mask_base)) / float(changed_mask_base.size)

        self.prev_np = curr_np

        # Full scene change check (e.g., tab switch)
        if baseline_delta_ratio >= self.full_scene_threshold:
            self.stable_baseline_np = curr_np
            self.last_motion_time = now
            self.observing_start_time = None
            self.motion_consecutive_hits = 0
            self.state = SentinelState.MOTION
            return SentinelResult(
                state=SentinelState.MOTION,
                frame_delta_ratio=frame_delta_ratio,
                baseline_delta_ratio=baseline_delta_ratio,
                stable_duration_sec=0.0,
                message="Full scene change detected; baseline reset"
            )

        # Dual-threshold motion hysteresis logic
        if self.state == SentinelState.MOTION:
            if frame_delta_ratio >= self.motion_exit_threshold:
                self.last_motion_time = now
                return SentinelResult(
                    state=SentinelState.MOTION,
                    frame_delta_ratio=frame_delta_ratio,
                    baseline_delta_ratio=baseline_delta_ratio,
                    stable_duration_sec=0.0,
                    message="Motion continuing"
                )
        else:
            if frame_delta_ratio >= self.motion_enter_threshold:
                self.motion_consecutive_hits += 1
                if self.motion_consecutive_hits >= self.motion_hits_threshold:
                    self.last_motion_time = now
                    self.observing_start_time = None
                    self.state = SentinelState.MOTION
                    return SentinelResult(
                        state=SentinelState.MOTION,
                        frame_delta_ratio=frame_delta_ratio,
                        baseline_delta_ratio=baseline_delta_ratio,
                        stable_duration_sec=0.0,
                        message="Motion detected (hysteresis triggered)"
                    )
            else:
                self.motion_consecutive_hits = 0

        # Screen is physically quiet
        stable_duration = now - self.last_motion_time

        if stable_duration < self.stable_duration_sec:
            self.state = SentinelState.STABLE
            return SentinelResult(
                state=SentinelState.STABLE,
                frame_delta_ratio=frame_delta_ratio,
                baseline_delta_ratio=baseline_delta_ratio,
                stable_duration_sec=stable_duration,
                message="Screen stabilizing..."
            )

        # Update stable baseline tracking
        if self.observing_start_time is None:
            self.observing_start_time = now

        observing_duration = now - self.observing_start_time

        # Extract downsampled bounding box
        bboxes = extract_candidate_regions(changed_mask_base)
        original_rect = None
        crop_img = None
        signals_res = None

        if bboxes:
            ds_bbox = bboxes[0]
            analyzed_h, analyzed_w, _ = curr_np.shape
            original_rect = scale_and_clamp_bbox(ds_bbox, (analyzed_w, analyzed_h), (orig_w, orig_h), padding=20)

            # Crop original QImage payload if bbox is valid
            if not original_rect.isEmpty() and original_rect.width() > 10 and original_rect.height() > 10:
                crop_img = qimage.copy(original_rect)

            is_persistent = observing_duration >= self.observation_duration_sec
            signals_res = self.signal_evaluator.evaluate_signals(
                curr_np=curr_np,
                base_np=self.stable_baseline_np,
                bbox=ds_bbox,
                is_persistent=is_persistent,
                is_scene_change=False,
                is_sustained_motion=False
            )

        # Check persistent difference against stable baseline
        if baseline_delta_ratio >= 0.003: # 0.3% persistent difference
            if observing_duration >= self.observation_duration_sec:
                self.state = SentinelState.CANDIDATE
                score_val = signals_res.composite_score if signals_res else 3
                msg = f"Escalation candidate detected (delta={baseline_delta_ratio*100:.1f}%, score={score_val})"
            else:
                self.state = SentinelState.OBSERVING
                msg = f"Observing persistent anomaly ({observing_duration:.1f}s / {self.observation_duration_sec:.1f}s)"
        else:
            self.stable_baseline_np = curr_np
            self.state = SentinelState.STABLE
            msg = "Screen stable; baseline updated"

        return SentinelResult(
            state=self.state,
            frame_delta_ratio=frame_delta_ratio,
            baseline_delta_ratio=baseline_delta_ratio,
            stable_duration_sec=stable_duration,
            message=msg,
            original_bbox=original_rect,
            crop_image=crop_img,
            signals=signals_res
        )

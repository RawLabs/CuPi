import time
import hashlib
from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from PyQt6.QtCore import QRect, Qt
from PyQt6.QtGui import QImage
from capture.sentinel_regions import compute_iou

class CandidateState(Enum):
    LATCHED = auto()
    TOAST_VISIBLE = auto()
    SUPPRESSED = auto()
    INSPECTION_PENDING = auto()

@dataclass
class CandidateRecord:
    fingerprint: str
    crop_image: Optional[QImage]
    original_bbox: QRect
    app_id: str
    title: str
    perceptual_hash: int
    first_seen: float
    last_seen: float
    missing_hits: int
    score: int
    state: CandidateState

def compute_stable_fingerprint(app_id: str, title: str, bbox: QRect) -> str:
    """Computes a process-stable SHA-256 fingerprint hash."""
    norm_title = title.strip().split(" - ")[0] if title else "App"
    material = f"{app_id}:{norm_title}:{bbox.x() // 10},{bbox.y() // 10},{bbox.width() // 10},{bbox.height() // 10}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]

def compute_perceptual_hash(qimage: QImage) -> int:
    """Computes a 64-bit block average hash of a QImage."""
    if qimage.isNull() or qimage.width() < 4 or qimage.height() < 4:
        return 0

    scaled = qimage.scaled(
        8, 8,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.FastTransformation
    )
    gray = scaled.convertToFormat(QImage.Format.Format_Grayscale8)

    pixels = []
    ptr = gray.bits()
    ptr.setsize(64)
    pixels = list(ptr.asstring())

    avg = sum(pixels) / 64.0 if pixels else 0.0
    hash_val = 0
    for idx, px in enumerate(pixels):
        if px >= avg:
            hash_val |= (1 << idx)
    return hash_val

def hamming_distance(hash1: int, hash2: int) -> int:
    """Computes Hamming distance between two 64-bit integer hashes."""
    return bin(hash1 ^ hash2).count('1')

class LatchedCandidateManager:
    """
    Manages latched candidate regions, disappearance hysteresis, global mute timers,
    and single-toast emissions to eliminate 2-second repeat log loops.
    """
    def __init__(self, missing_hits_threshold: int = 3, mute_duration_sec: float = 300.0):
        self.missing_hits_threshold = missing_hits_threshold
        self.mute_duration_sec = mute_duration_sec

        self.active_candidates: Dict[str, CandidateRecord] = {}
        self.suppressed_fingerprints: set = set()
        self.mute_until_time: float = 0.0

    def is_muted(self) -> bool:
        return time.monotonic() < self.mute_until_time

    def set_mute_5m(self):
        self.mute_until_time = time.monotonic() + self.mute_duration_sec
        # Release crop images for active candidates during mute to save memory
        for record in self.active_candidates.values():
            record.crop_image = None

    def suppress_fingerprint(self, fingerprint: str):
        self.suppressed_fingerprints.add(fingerprint)
        if fingerprint in self.active_candidates:
            self.active_candidates[fingerprint].state = CandidateState.SUPPRESSED
            self.active_candidates[fingerprint].crop_image = None

    def process_candidate(
        self,
        app_id: str,
        title: str,
        bbox: QRect,
        crop_image: QImage,
        score: int,
        timestamp: float = 0.0
    ) -> Tuple[Optional[CandidateRecord], bool]:
        """
        Evaluates a candidate. Returns (candidate_record, should_emit_toast).
        """
        now = time.monotonic() if timestamp == 0.0 else timestamp
        p_hash = compute_perceptual_hash(crop_image)
        norm_title = title.strip().split(" - ")[0] if title else "App"

        # Check existing active candidates for a match
        matched_fingerprint = None
        for fp, record in list(self.active_candidates.items()):
            if record.app_id == app_id:
                title_match = (record.title == norm_title) or (norm_title in record.title) or (record.title in norm_title)
                iou = compute_iou(record.original_bbox, bbox)
                h_dist = hamming_distance(record.perceptual_hash, p_hash)

                if title_match and iou >= 0.50 and h_dist <= 8:
                    matched_fingerprint = fp
                    break

        if matched_fingerprint:
            # Update existing candidate
            record = self.active_candidates[matched_fingerprint]
            record.last_seen = now
            record.missing_hits = 0
            record.original_bbox = bbox
            record.score = score

            should_emit_toast = False
            if record.state == CandidateState.TOAST_VISIBLE and not self.is_muted() and score >= 3:
                record.state = CandidateState.LATCHED
                should_emit_toast = True

            if not self.is_muted() and record.state != CandidateState.SUPPRESSED:
                record.crop_image = crop_image  # Keep fresh crop

            return record, should_emit_toast

        # Brand new unique candidate
        fp = compute_stable_fingerprint(app_id, norm_title, bbox)
        is_suppressed = fp in self.suppressed_fingerprints or self.is_muted()

        should_emit_toast = (not is_suppressed and score >= 3)
        initial_state = CandidateState.SUPPRESSED if is_suppressed else (CandidateState.LATCHED if should_emit_toast else CandidateState.TOAST_VISIBLE)

        record = CandidateRecord(
            fingerprint=fp,
            crop_image=None if is_suppressed else crop_image,
            original_bbox=bbox,
            app_id=app_id,
            title=norm_title,
            perceptual_hash=p_hash,
            first_seen=now,
            last_seen=now,
            missing_hits=0,
            score=score,
            state=initial_state
        )

        self.active_candidates[fp] = record
        return record, should_emit_toast

    def update_frame_tick(self, observed_fingerprints: List[str]):
        """
        Applies disappearance hysteresis. Increments missing_hits for unobserved candidates.
        Clears candidates after 3 consecutive missing frames.
        """
        for fp, record in list(self.active_candidates.items()):
            if fp not in observed_fingerprints:
                record.missing_hits += 1
                if record.missing_hits >= self.missing_hits_threshold:
                    record.crop_image = None
                    del self.active_candidates[fp]

    def clear_all(self):
        for record in self.active_candidates.values():
            record.crop_image = None
        self.active_candidates.clear()
        self.suppressed_fingerprints.clear()

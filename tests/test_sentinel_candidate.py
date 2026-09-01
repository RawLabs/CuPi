import unittest
import time
from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage, QColor
from sentinel.sentinel_candidate import (
    LatchedCandidateManager, CandidateState, compute_stable_fingerprint,
    compute_perceptual_hash, hamming_distance
)

class TestSentinelCandidate(unittest.TestCase):
    def create_test_image(self, width: int = 64, height: int = 64, color: QColor = QColor(200, 50, 50)) -> QImage:
        img = QImage(width, height, QImage.Format.Format_RGB888)
        img.fill(color)
        return img

    def test_stable_fingerprint_across_process_runs(self):
        fp1 = compute_stable_fingerprint("app123", "Terminal - main.py", QRect(100, 200, 300, 150))
        fp2 = compute_stable_fingerprint("app123", "Terminal - main.py", QRect(100, 200, 300, 150))
        self.assertEqual(fp1, fp2)
        self.assertEqual(len(fp1), 24)

    def test_candidate_requires_matching_application(self):
        mgr = LatchedCandidateManager()
        bbox = QRect(100, 100, 200, 200)
        img = self.create_test_image()

        rec1, toast1 = mgr.process_candidate("terminal", "Bash", bbox, img, score=5, timestamp=1.0)
        self.assertTrue(toast1)

        # Candidate at same coords but different app
        rec2, toast2 = mgr.process_candidate("firefox", "Browser", bbox, img, score=5, timestamp=2.0)
        self.assertTrue(toast2)
        self.assertNotEqual(rec1.fingerprint, rec2.fingerprint)

    def test_candidate_survives_one_missing_frame(self):
        mgr = LatchedCandidateManager(missing_hits_threshold=3)
        bbox = QRect(100, 100, 200, 200)
        img = self.create_test_image()

        rec, _ = mgr.process_candidate("app1", "Terminal", bbox, img, score=5, timestamp=1.0)
        fp = rec.fingerprint

        # Frame 1: missing
        mgr.update_frame_tick([])
        self.assertIn(fp, mgr.active_candidates)

        # Frame 2: missing
        mgr.update_frame_tick([])
        self.assertIn(fp, mgr.active_candidates)

        # Frame 3: missing -> should be cleared
        mgr.update_frame_tick([])
        self.assertNotIn(fp, mgr.active_candidates)

    def test_mute_releases_crop_but_retains_metadata(self):
        mgr = LatchedCandidateManager()
        bbox = QRect(100, 100, 200, 200)
        img = self.create_test_image()

        rec, _ = mgr.process_candidate("app1", "Terminal", bbox, img, score=5, timestamp=1.0)
        self.assertIsNotNone(rec.crop_image)

        mgr.set_mute_5m()
        self.assertTrue(mgr.is_muted())
        self.assertIsNone(rec.crop_image)

    def test_crop_hash_tolerates_cursor_blink(self):
        img1 = self.create_test_image(color=QColor(100, 100, 100))
        img2 = self.create_test_image(color=QColor(100, 100, 100))
        # Add micro blinking pixel
        img2.setPixelColor(10, 10, QColor(255, 255, 255))

        h1 = compute_perceptual_hash(img1)
        h2 = compute_perceptual_hash(img2)
        dist = hamming_distance(h1, h2)
        self.assertLessEqual(dist, 6)

if __name__ == "__main__":
    unittest.main()

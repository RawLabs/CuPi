import time
import unittest
import numpy as np
from PyQt6.QtGui import QImage, QColor
from capture.sentinel_engine import SentinelEngine, SentinelState

class TestSentinelEngine(unittest.TestCase):
    def create_solid_image(self, width: int = 100, height: int = 100, color: QColor = QColor(250, 250, 250)) -> QImage:
        img = QImage(width, height, QImage.Format.Format_RGB888)
        img.fill(color)
        return img

    def test_delta_ratio_is_channel_bounded(self):
        engine = SentinelEngine()
        img1 = self.create_solid_image(color=QColor(0, 0, 0))
        img2 = self.create_solid_image(color=QColor(255, 255, 255))

        res1 = engine.process_frame(img1, timestamp=1.0)
        res2 = engine.process_frame(img2, timestamp=2.0)

        # Inverted image should yield 1.0 (100% changed), never > 1.0
        self.assertLessEqual(res2.frame_delta_ratio, 1.0)
        self.assertGreater(res2.frame_delta_ratio, 0.99)

    def test_stable_baseline_not_updated_during_motion(self):
        engine = SentinelEngine(motion_threshold=0.015, stable_duration_sec=4.0)
        img_black = self.create_solid_image(color=QColor(0, 0, 0))
        img_white = self.create_solid_image(color=QColor(255, 255, 255))

        engine.process_frame(img_black, timestamp=1.0)
        # Alternate frames continuously to simulate motion
        res1 = engine.process_frame(img_white, timestamp=2.0)
        res2 = engine.process_frame(img_black, timestamp=3.0)

        self.assertEqual(res1.state, SentinelState.MOTION)
        self.assertEqual(res2.state, SentinelState.MOTION)

    def test_full_scene_change_resets_baseline(self):
        engine = SentinelEngine(full_scene_threshold=0.35)
        img1 = self.create_solid_image(color=QColor(10, 10, 10))
        img2 = self.create_solid_image(color=QColor(200, 200, 200))

        engine.process_frame(img1, timestamp=1.0)
        res = engine.process_frame(img2, timestamp=2.0)

        self.assertEqual(res.state, SentinelState.MOTION)
        self.assertIn("Full scene change", res.message)

    def test_candidate_detection_after_observation(self):
        engine = SentinelEngine(
            motion_threshold=0.015,
            stable_duration_sec=2.0,
            observation_duration_sec=2.0
        )
        img_base = self.create_solid_image(color=QColor(50, 50, 50))
        # Image with a persistent red square region
        img_anomaly = self.create_solid_image(color=QColor(50, 50, 50))
        for x in range(20, 60):
            for y in range(20, 60):
                img_anomaly.setPixelColor(x, y, QColor(240, 20, 20))

        # Initial frame
        engine.process_frame(img_base, timestamp=1.0)

        # Screen stabilizes for 2.5s
        res_stable = engine.process_frame(img_base, timestamp=3.5)
        self.assertEqual(res_stable.state, SentinelState.STABLE)

        # Anomaly appears at t=4.0
        res_motion = engine.process_frame(img_anomaly, timestamp=4.0)

        # Screen settles with persistent anomaly at t=7.0
        res_obs = engine.process_frame(img_anomaly, timestamp=7.0)
        self.assertIn(res_obs.state, [SentinelState.OBSERVING, SentinelState.CANDIDATE])

        # At t=9.5 (> 2.0s observation duration) -> CANDIDATE
        res_cand = engine.process_frame(img_anomaly, timestamp=9.5)
        self.assertEqual(res_cand.state, SentinelState.CANDIDATE)
        self.assertIn("Escalation candidate", res_cand.message)

    def test_large_image_scaling_does_not_throw(self):
        engine = SentinelEngine()
        # 1920x1080 large full-HD image
        large_img = self.create_solid_image(width=1920, height=1080, color=QColor(128, 128, 128))
        res = engine.process_frame(large_img, timestamp=1.0)
        self.assertEqual(res.state, SentinelState.STABLE)

if __name__ == "__main__":
    unittest.main()

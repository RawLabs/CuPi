import unittest
from PySide6.QtGui import QImage, QColor
from capture.sentinel_engine import SentinelEngine, SentinelState

class TestSentinelHysteresis(unittest.TestCase):
    def create_solid_image(self, width: int = 100, height: int = 100, color: QColor = QColor(50, 50, 50)) -> QImage:
        img = QImage(width, height, QImage.Format.Format_RGB888)
        img.fill(color)
        return img

    def test_dual_threshold_hysteresis_ignores_minor_cursor_jitter(self):
        engine = SentinelEngine(
            motion_enter_threshold=0.030, # 3% to enter
            motion_exit_threshold=0.012,  # 1.2% to exit
            motion_hits_threshold=2
        )
        base = self.create_solid_image()

        # Initial frame
        engine.process_frame(base, timestamp=1.0)
        res_stable = engine.process_frame(base, timestamp=3.0)
        self.assertEqual(res_stable.state, SentinelState.STABLE)

        # Micro-jitter frame (1.8% change - below 3.0% enter threshold)
        jitter_img = self.create_solid_image()
        for x in range(5, 12):
            for y in range(5, 12):
                jitter_img.setPixelColor(x, y, QColor(200, 200, 200))

        res_jitter = engine.process_frame(jitter_img, timestamp=3.5)
        # Should stay in STABLE, not enter MOTION
        self.assertNotEqual(res_jitter.state, SentinelState.MOTION)

if __name__ == "__main__":
    unittest.main()

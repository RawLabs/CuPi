import unittest
import numpy as np
from capture.sentinel_signals import SentinelSignalEvaluator

class TestSentinelSignals(unittest.TestCase):
    def test_composite_scoring_and_red_detection(self):
        evaluator = SentinelSignalEvaluator()

        # 100x100 RGB image with a red exception block
        curr_np = np.zeros((100, 100, 3), dtype=np.uint8)
        curr_np[20:60, 20:60] = [220, 20, 20] # Red accent

        base_np = np.zeros((100, 100, 3), dtype=np.uint8) # Plain black baseline

        res = evaluator.evaluate_signals(
            curr_np=curr_np,
            base_np=base_np,
            bbox=(20, 20, 40, 40),
            is_persistent=True,
            is_scene_change=False,
            is_sustained_motion=False
        )

        self.assertTrue(res.has_new_red)
        self.assertGreaterEqual(res.composite_score, 4)

    def test_non_red_persistent_error_qualifies(self):
        evaluator = SentinelSignalEvaluator()

        # 100x100 image with text-like edge pattern (white text on dark background)
        curr_np = np.zeros((100, 100, 3), dtype=np.uint8)
        for y in range(10, 90, 4):
            for x in range(10, 90, 2):
                curr_np[y, x] = [240, 240, 240]

        base_np = np.zeros((100, 100, 3), dtype=np.uint8)

        res = evaluator.evaluate_signals(
            curr_np=curr_np,
            base_np=base_np,
            bbox=(10, 10, 80, 80),
            is_persistent=True,
            is_scene_change=False,
            is_sustained_motion=False
        )

        self.assertTrue(res.has_text_like_edges)
        # Persistent (+3) + Text edges (+1) = 4 >= 4 (qualifies for toast!)
        self.assertGreaterEqual(res.composite_score, 4)

if __name__ == "__main__":
    unittest.main()

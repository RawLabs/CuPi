import unittest
from PySide6.QtCore import QRect
from capture.sentinel_regions import scale_and_clamp_bbox, compute_iou

class TestSentinelRegions(unittest.TestCase):
    def test_bbox_padding_clamps_at_each_screen_edge(self):
        analyzed_size = (480, 270)
        original_size = (1920, 1080)

        # 1. Top-Left corner (0, 0)
        bbox_top_left = (0, 0, 40, 40)
        rect_tl = scale_and_clamp_bbox(bbox_top_left, analyzed_size, original_size, padding=20)
        self.assertEqual(rect_tl.x(), 0)
        self.assertEqual(rect_tl.y(), 0)
        self.assertGreater(rect_tl.width(), 0)
        self.assertGreater(rect_tl.height(), 0)

        # 2. Bottom-Right corner (470, 260)
        bbox_br = (440, 240, 40, 30)
        rect_br = scale_and_clamp_bbox(bbox_br, analyzed_size, original_size, padding=20)
        self.assertLessEqual(rect_br.x() + rect_br.width(), 1920)
        self.assertLessEqual(rect_br.y() + rect_br.height(), 1080)

    def test_iou_calculation(self):
        r1 = QRect(100, 100, 200, 200)
        r2 = QRect(150, 100, 200, 200)

        iou = compute_iou(r1, r2)
        self.assertGreater(iou, 0.40)
        self.assertLess(iou, 1.0)

        # Disjoint rects
        r3 = QRect(600, 600, 50, 50)
        self.assertEqual(compute_iou(r1, r3), 0.0)

if __name__ == "__main__":
    unittest.main()

import unittest
from PySide6.QtGui import QPixmap, QColor
from ai.conversation import parse_annotations
from capture.annotation_utils import draw_annotation_on_pixmap

class TestAnnotations(unittest.TestCase):
    def test_parse_double_tuple_box_annotations(self):
        raw_text = '<annotate type="box" image="1">[(725, 185), (935, 255)]</annotate>'
        clean_text, annotations = parse_annotations(raw_text)

        self.assertNotIn("<annotate>", clean_text)
        self.assertNotIn("[(725, 185)", clean_text)
        self.assertEqual(len(annotations), 1)
        ann = annotations[0]
        self.assertEqual(ann["type"], "box")
        self.assertEqual(ann["coords"], [725, 185, 935, 255])

    def test_draw_annotation_box_on_pixmap(self):
        pix = QPixmap(1704, 1065)
        pix.fill(QColor(40, 40, 40))

        annotated = draw_annotation_on_pixmap(pix, "box", [725, 185, 935, 255], is_normalized=True)
        self.assertFalse(annotated.isNull())
        self.assertEqual(annotated.width(), 1704)
        self.assertEqual(annotated.height(), 1065)

if __name__ == "__main__":
    unittest.main()

import os
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QColor
from config import ConfigManager
from ai.conversation import ConversationSession
from capture.screen_capture import SourceTarget, pixmap_to_b64, list_screens, list_windows

# Ensure offscreen Qt platform for headless tests
os.environ["QT_QPA_PLATFORM"] = "offscreen"
_app = QApplication.instance() or QApplication([])


class TestCompanion(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        from storage import create_storage_backend

        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        (base / "portable.flag").touch()
        storage = create_storage_backend(base)
        for target, value in (("config._DEFAULT_STORAGE", storage),
                              ("config.CONFIG_FILE", storage.layout.config / "config.json")):
            patcher = patch(target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        # UI tests must not contact a live provider or leave request threads.
        patcher = patch("ui.companion_window.CompanionWindow.fetch_models")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_config_manager(self):
        cm = ConfigManager()
        cm.set("test_key", "test_val")
        self.assertEqual(cm.get("test_key"), "test_val")

    def test_conversation_history(self):
        conv = ConversationSession(max_turns=3)
        conv.add_user_message("Turn 1", image_b64="fake_b64")
        conv.add_assistant_message("Ans 1")
        conv.add_user_message("Turn 2")

        msgs = conv.get_openai_messages("Turn 3 prompt", current_image_b64="img3")
        self.assertEqual(msgs[0]["role"], "system")
        self.assertEqual(msgs[-1]["role"], "user")
        # Current user message has content list
        self.assertIsInstance(msgs[-1]["content"], list)
        self.assertEqual(msgs[-1]["content"][0]["text"], "Turn 3 prompt")
        self.assertIn("data:image/png;base64,img3", msgs[-1]["content"][1]["image_url"]["url"])

    def test_multi_image_conversation_session(self):
        conv = ConversationSession(max_turns=3)
        conv.add_user_message("Check 2 images", images_b64=["img1_b64", "img2_b64"])
        msgs = conv.get_openai_messages()
        self.assertEqual(len(msgs), 2)
        user_msg_content = msgs[1]["content"]
        self.assertEqual(len(user_msg_content), 3) # 1 text + 2 images
        self.assertEqual(user_msg_content[0]["text"], "Check 2 images")
        self.assertIn("img1_b64", user_msg_content[1]["image_url"]["url"])
        self.assertIn("img2_b64", user_msg_content[2]["image_url"]["url"])

    def test_pixmap_b64_encoding(self):
        pix = QPixmap(100, 100)
        pix.fill(QColor(255, 0, 0))
        b64_str = pixmap_to_b64(pix)
        self.assertTrue(len(b64_str) > 50)

    def test_large_pixmap_scaling(self):
        pix = QPixmap(2000, 2000)
        pix.fill(QColor(0, 255, 0))
        b64_str = pixmap_to_b64(pix, max_dim=1000)
        self.assertTrue(len(b64_str) > 50)

    def test_source_listing(self):
        screens = list_screens()
        self.assertTrue(len(screens) >= 1)
        self.assertEqual(screens[0].target_type, "screen")

    def test_native_area_picker_geometry_is_global(self):
        from capture.picker_overlay import PickerOverlay

        rect = PickerOverlay._parse_native_geometry("-320,24 640x480\n")
        self.assertIsNotNone(rect)
        self.assertEqual((rect.x(), rect.y(), rect.width(), rect.height()), (-320, 24, 640, 480))
        self.assertIsNone(PickerOverlay._parse_native_geometry("not a geometry"))

    def test_window_capture_cropping(self):
        from PySide6.QtCore import QRect
        from unittest.mock import patch
        from platform_api.linux_wayland import LinuxWaylandBackend
        target = SourceTarget(
            target_type="window",
            target_id="0x123456",
            name="Test Window",
            rect=QRect(10, 10, 200, 200)
        )
        backend = LinuxWaylandBackend()
        # Source checkouts still work without the packaged clean-window helper.
        # They use an explicitly communicated compositor region capture.
        visible = QPixmap(200, 200)
        with patch.object(backend, "_toplevel_capture_helper", return_value=None), patch.object(
            backend, "capture_region", return_value=visible
        ) as capture_region:
            self.assertIs(backend.capture_window(target), visible)
            capture_region.assert_called_once_with(target.rect)
            self.assertIn("visible window region", backend.last_capture_notice)

    def test_window_group_capture_is_one_spatial_composite(self):
        from PySide6.QtCore import QRect
        from ui.companion_window import CompanionWindow

        first = SourceTarget("window", "first", "First", QRect(10, 20, 100, 50))
        second = SourceTarget("window", "second", "Second", QRect(140, 40, 50, 40))
        first_image = QPixmap(100, 50)
        first_image.fill(QColor("red"))
        second_image = QPixmap(50, 40)
        second_image.fill(QColor("blue"))

        composite = CompanionWindow._compose_window_captures([
            (first, first_image),
            (second, second_image),
        ])

        self.assertIsNotNone(composite)
        self.assertEqual((composite.width(), composite.height()), (180, 60))
        self.assertTrue(composite.hasAlphaChannel())

    def test_companion_window_ui(self):
        from ui.companion_window import CompanionWindow
        cm = ConfigManager()
        win = CompanionWindow(cm)
        win.scroll_to_bottom()
        win.clear_chat()
        self.assertTrue(win.centralWidget() is not None)
        win.close()

    def test_full_screen_capture_mode_selects_screen(self):
        from ui.companion_window import CompanionWindow

        win = CompanionWindow(ConfigManager())
        # A manually selected area or window must be replaced by a screen target.
        win.active_target = SourceTarget("region", "custom_region", "Selected Area")
        win._select_full_screen()
        self.assertIsNotNone(win.active_target)
        self.assertEqual(win.active_target.target_type, "screen")
        self.assertEqual(win.source_combo.currentData(), win.active_target)
        win.close()

    def test_model_search_filtering(self):
        from ui.companion_window import CompanionWindow
        cm = ConfigManager()
        win = CompanionWindow(cm)
        win.all_models = [
            {"id": "openai/gpt-4o", "is_vision": True, "is_free": False},
            {"id": "google/gemini-2.0-flash-001", "is_vision": True, "is_free": False},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "is_vision": False, "is_free": True},
            {"id": "qwen/qwen-2-vl-72b-instruct:free", "is_vision": True, "is_free": True}
        ]
        
        # Default vision filter active: non-vision models excluded
        win._filter_models()
        self.assertEqual(win.model_combo.count(), 3)

        # Test free toggle button with vision filter
        win.free_filter_btn.setChecked(True)
        self.assertEqual(win.model_combo.count(), 1)
        self.assertEqual(win.model_combo.itemText(0), "qwen/qwen-2-vl-72b-instruct:free")

        # Search is adjacent to the model selector and understands capabilities,
        # even when a provider does not include the word in the model ID.
        win.free_filter_btn.setChecked(False)
        win.model_search_input.setText("free")
        self.assertEqual(win.model_combo.count(), 1)
        self.assertEqual(win.model_combo.itemText(0), "qwen/qwen-2-vl-72b-instruct:free")
        win.close()

    def test_chat_message_renders_markdown(self):
        from ui.components import ChatMessageWidget
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QLabel

        widget = ChatMessageWidget("assistant", "### Heading\n\n**Bold** and `code`")
        body = widget.findChild(QLabel, "MessageText")
        self.assertIsNotNone(body)
        self.assertEqual(body.textFormat(), Qt.TextFormat.MarkdownText)

    def test_window_opacity_slider(self):
        from ui.companion_window import CompanionWindow
        cm = ConfigManager()
        win = CompanionWindow(cm)
        # Initial opacity on launch must be 100%
        self.assertEqual(win.opacity_slider.value(), 100)
        self.assertAlmostEqual(win.windowOpacity(), 1.0, delta=0.01)
        self.assertEqual(win.opacity_label.text(), "100%")

        # Test adjusting slider
        win.opacity_slider.setValue(70)
        self.assertAlmostEqual(win.windowOpacity(), 0.7, delta=0.05)
        self.assertEqual(win.opacity_label.text(), "70%")
        self.assertEqual(cm.get("window_opacity"), 70)
        win.close()

    def test_window_toggle_collapse(self):
        from ui.companion_window import CompanionWindow
        cm = ConfigManager()
        win = CompanionWindow(cm)
        # Collapse
        win.toggle_collapse()
        self.assertTrue(win.is_collapsed)
        self.assertEqual(win.height(), 40)
        self.assertTrue(win.content_area.isHidden())

        # Expand
        win.toggle_collapse()
        self.assertFalse(win.is_collapsed)
        self.assertFalse(win.content_area.isHidden())
        self.assertTrue(win.height() >= 720)
        win.close()

    def test_save_screen_to_disk(self):
        from ui.companion_window import CompanionWindow
        from PySide6.QtGui import QPixmap, QColor
        import tempfile
        from pathlib import Path

        cm = ConfigManager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            cm.set("captures_dir", tmp_dir)
            win = CompanionWindow(cm)
            pix = QPixmap(100, 100)
            pix.fill(QColor(0, 0, 255))
            
            # Step 1
            saved_path_1 = win._save_pixmap_to_disk(pix)
            self.assertIsNotNone(saved_path_1)
            self.assertIn("capture_step_01_", saved_path_1)
            self.assertTrue(Path(saved_path_1).exists())

            # Step 2
            saved_path_2 = win._save_pixmap_to_disk(pix)
            self.assertIsNotNone(saved_path_2)
            self.assertIn("capture_step_02_", saved_path_2)
            self.assertTrue(Path(saved_path_2).exists())
            win.close()

    def test_save_screenshot_does_not_attach_to_next_query(self):
        from ui.companion_window import CompanionWindow
        import tempfile
        from pathlib import Path

        class FakePlatform:
            def active_window(self):
                return None

            def activate_window(self, target):
                return None

            def capture_target(self, target):
                pix = QPixmap(100, 100)
                pix.fill(QColor(0, 0, 255))
                return pix

        cm = ConfigManager()
        with tempfile.TemporaryDirectory() as tmp_dir:
            cm.set("captures_dir", tmp_dir)
            win = CompanionWindow(cm)
            win.platform = FakePlatform()
            win.active_target = SourceTarget("screen", "screen_0", "Screen 1")

            win.capture_and_save_screen()

            self.assertEqual(win.attached_pixmaps, [])
            self.assertEqual(win.attached_images_b64, [])
            self.assertEqual(len(list(Path(tmp_dir).glob("capture_step_01_*.png"))), 1)
            win.close()

    def test_multi_image_conversation_bubble(self):
        from ui.components import ChatMessageWidget
        from PySide6.QtGui import QPixmap, QColor
        pix1 = QPixmap(100, 100)
        pix1.fill(QColor(255, 0, 0))
        pix2 = QPixmap(100, 100)
        pix2.fill(QColor(0, 255, 0))
        
        widget = ChatMessageWidget("user", "Test multi image", pixmaps=[pix1, pix2])
        self.assertIsNotNone(widget)

    def test_finalized_doc_export(self):
        from export.document_exporter import DocumentExporter
        from PySide6.QtGui import QPixmap, QColor
        import tempfile
        from pathlib import Path

        pix1 = QPixmap(100, 100)
        pix1.fill(QColor(255, 0, 0))
        pix2 = QPixmap(100, 100)
        pix2.fill(QColor(0, 255, 0))

        text = "1. **Open Settings** (see **[Image 1]**)\n2. **Select Models** (see **[Image 2]**)"

        with tempfile.TemporaryDirectory() as tmp_dir:
            res = DocumentExporter.export_finalized_doc(
                text,
                [pix1, pix2],
                title="Test_SOP_Export",
                custom_export_dir=tmp_dir
            )
            self.assertTrue(Path(res["md_path"]).exists())
            self.assertTrue(Path(res["html_path"]).exists())
            
            with open(res["md_path"], "r", encoding="utf-8") as f:
                md_data = f.read()
                self.assertIn("![Step 1 Screenshot](./images/step_01.png)", md_data)
                self.assertIn("![Step 2 Screenshot](./images/step_02.png)", md_data)

    def test_parse_annotations(self):
        from ai.conversation import parse_annotations
        raw = "Click settings <annotate type=\"arrow\" image=\"2\">[(150, 250)]</annotate> or check <point image=\"1\">[(50, 60)]</point>"
        clean, anns = parse_annotations(raw)
        self.assertEqual(clean, "Click settings  or check")
        self.assertEqual(len(anns), 2)
        self.assertEqual(anns[0]["type"], "arrow")
        self.assertEqual(anns[0]["image_index"], 2)
        self.assertEqual(anns[0]["coords"], [150, 250])
        self.assertEqual(anns[1]["type"], "circle")
        self.assertEqual(anns[1]["image_index"], 1)

    def test_annotation_drawing(self):
        from capture.annotation_utils import draw_annotation_on_pixmap
        from PySide6.QtGui import QPixmap, QColor
        pix = QPixmap(200, 200)
        pix.fill(QColor(255, 255, 255))
        
        for shape in ["circle", "box", "crosshair", "arrow"]:
            annotated = draw_annotation_on_pixmap(pix, shape, [100, 100])
            self.assertFalse(annotated.isNull())

    def test_annotation_dialog_init(self):
        from capture.annotation_dialog import AnnotationDialog
        from PySide6.QtGui import QPixmap, QColor
        pix = QPixmap(200, 200)
        pix.fill(QColor(255, 255, 255))
        dlg = AnnotationDialog(pix)
        self.assertIsNotNone(dlg.canvas)
        res_pixmap = dlg.get_result_pixmap()
        self.assertFalse(res_pixmap.isNull())


if __name__ == "__main__":
    unittest.main()

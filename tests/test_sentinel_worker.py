import time
import unittest
from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer
from PyQt6.QtGui import QImage, QColor
from capture.sentinel_engine import SentinelState
from sentinel.sentinel_worker import SentinelController

class TestSentinelWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QCoreApplication.instance():
            cls.app = QCoreApplication([])
        else:
            cls.app = QCoreApplication.instance()

    def test_worker_frame_processing_and_shutdown(self):
        controller = SentinelController()
        try:
            received_results = []

            def on_result(res, meta):
                received_results.append((res, meta))

            controller.worker.result_ready.connect(on_result)

            # Create a test image
            img = QImage(100, 100, QImage.Format.Format_RGB888)
            img.fill(QColor(100, 100, 100))

            # Send frame to worker thread
            controller.send_frame(img, {"timestamp": 1.0})

            # Wait briefly for thread execution via QEventLoop
            loop = QEventLoop()
            QTimer.singleShot(200, loop.quit)
            loop.exec()

            self.assertEqual(len(received_results), 1)
            res, meta = received_results[0]
            self.assertEqual(res.state, SentinelState.STABLE)
            self.assertGreaterEqual(meta["metrics"].frames_processed, 1)
        finally:
            # Stop controller and thread
            controller.stop()
            self.assertFalse(controller.thread.isRunning())

if __name__ == "__main__":
    unittest.main()

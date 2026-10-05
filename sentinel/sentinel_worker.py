import time
from PySide6.QtCore import QObject, Slot, Signal, QThread, QCoreApplication
from PySide6.QtGui import QImage
from capture.sentinel_engine import SentinelEngine, SentinelResult, SentinelMetrics, SentinelState
from sentinel.sentinel_candidate import LatchedCandidateManager, CandidateRecord

class SentinelWorker(QObject):
    """
    QObject-based Sentinel Worker designed to run on a dedicated QThread.
    Consumes copied QImage frames sent from the main GUI thread.
    Integrates LatchedCandidateManager to suppress candidate loop spam.
    """
    result_ready = Signal(object, dict)               # (SentinelResult, metadata)
    candidate_toast_triggered = Signal(object)        # (CandidateRecord)
    processing_finished = Signal()                    # Signal back to GUI thread

    def __init__(self, motion_enter_threshold: float = 0.030, full_scene_threshold: float = 0.35):
        super().__init__()
        self.engine = SentinelEngine(
            motion_enter_threshold=motion_enter_threshold,
            full_scene_threshold=full_scene_threshold
        )
        self.metrics = SentinelMetrics()
        self.candidate_manager = LatchedCandidateManager()

    @Slot(QImage, dict)
    def process_frame(self, qimage: QImage, context: dict):
        start_time = time.monotonic()
        self.metrics.frames_processed += 1

        result = self.engine.process_frame(qimage, timestamp=context.get("timestamp", start_time))

        elapsed_ms = (time.monotonic() - start_time) * 1000.0
        if self.metrics.average_processing_ms == 0.0:
            self.metrics.average_processing_ms = elapsed_ms
        else:
            self.metrics.average_processing_ms = 0.8 * self.metrics.average_processing_ms + 0.2 * elapsed_ms

        meta = {
            "elapsed_ms": elapsed_ms,
            "metrics": self.metrics,
            "context": context
        }

        # Handle latched candidates & toast triggers
        observed_fingerprints = []
        if result.state == SentinelState.CANDIDATE and result.original_bbox and result.crop_image:
            app_id = context.get("target_id", "app")
            title = context.get("target_name", "Target Application")
            score = result.signals.composite_score if result.signals else 4

            record, should_toast = self.candidate_manager.process_candidate(
                app_id=app_id,
                title=title,
                bbox=result.original_bbox,
                crop_image=result.crop_image,
                score=score,
                timestamp=start_time
            )

            if record:
                observed_fingerprints.append(record.fingerprint)

            if should_toast and record:
                self.candidate_toast_triggered.emit(record)

        self.candidate_manager.update_frame_tick(observed_fingerprints)

        self.result_ready.emit(result, meta)
        self.processing_finished.emit()

    @Slot()
    def reset(self):
        self.engine.reset_baselines()
        self.candidate_manager.clear_all()


class SentinelController(QObject):
    """
    Controller managing the SentinelWorker and its owning QThread lifecycle.
    Created and owned by CompanionWindow on the GUI thread.
    """
    frame_dispatch = Signal(QImage, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thread = QThread(QCoreApplication.instance())
        self.worker = SentinelWorker()
        self.worker.moveToThread(self.thread)

        # Wire up internal signals
        self.frame_dispatch.connect(self.worker.process_frame)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def send_frame(self, qimage_copy: QImage, context: dict):
        self.frame_dispatch.emit(qimage_copy, context)

    def stop(self):
        if self.thread and self.thread.isRunning():
            self.thread.quit()
            self.thread.wait(1000)

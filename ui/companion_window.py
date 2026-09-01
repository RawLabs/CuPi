import sys
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QComboBox, QLineEdit, QScrollArea, QFrame, QDialog, QMessageBox, QSizeGrip, QSlider
)
from PyQt6.QtCore import Qt, QPoint, QRect, QSize, pyqtSlot, QTimer
from PyQt6.QtGui import QPixmap, QCursor, QIcon, QFont, QPainter

from config import ConfigManager
from ai.conversation import ConversationSession
from ai.provider_client import InferenceWorker, ModelFetchWorker
from capture.screen_capture import (
    SourceTarget, pixmap_to_b64
)
from platform_api import PlatformBackend, get_platform_backend
from capture.picker_overlay import PickerOverlay
from sentinel.sentinel_worker import SentinelController
from sentinel.sentinel_logger import SentinelLogger
from capture.sentinel_engine import SentinelState
import re
from export.document_exporter import DocumentExporter
from ui.styles import DARK_STYLE
from ui.components import ChatMessageWidget, AttachedImageBadge, PromptTextEdit
from ui.privacy_dialog import OpenRouterPrivacyDialog
from ui.sentinel_dialog import SentinelLogDialog
from ui.sentinel_toast import SentinelToastWidget


class CompanionWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager, platform_backend: PlatformBackend | None = None):
        super().__init__()
        self.config = config_manager
        self.platform = platform_backend or get_platform_backend()
        self.conversation = ConversationSession(
            max_turns=self.config.get("max_history_turns", 10)
        )

        self.drag_position = QPoint()
        self.is_collapsed = False
        self.is_resizing = False
        self.resize_edges = set()
        self.resize_start_pos = QPoint()
        self.resize_start_geometry = QRect()
        self.RESIZE_MARGIN = 8

        self.all_models: list = []
        self.active_target: Optional[SourceTarget] = None
        self.selected_targets: list[SourceTarget] = []
        self.preview_pixmaps: list[QPixmap] = []
        self.last_capture_targets: list[SourceTarget] = []
        self.last_capture_errors: list[str] = []
        self.attached_pixmaps: list[QPixmap] = []
        self.attached_images_b64: list = []
        self.last_sent_pixmaps: list = []
        self.capture_sequence: int = 0
        self.current_guide_type = "Work Instruction"
        self.pending_guide_type = self.current_guide_type
        self.last_guide_request = ""
        
        self.inference_worker: Optional[InferenceWorker] = None
        self.model_fetch_worker: Optional[ModelFetchWorker] = None

        self.sentinel_controller: Optional[SentinelController] = None
        self.sentinel_logger = SentinelLogger(storage=self.config.storage)
        self.sentinel_timer: QTimer = QTimer(self)
        self.sentinel_timer.setInterval(2000)
        self.sentinel_timer.timeout.connect(self._on_sentinel_timer)
        self._sentinel_busy: bool = False

        self._init_ui()
        self._load_saved_geometry()
        self._refresh_sources()
        self.fetch_models()

    def _init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumSize(460, 720)
        self.resize(460, 720)
        self.setMouseTracking(True)

        # Central widget container
        self.main_container = QWidget(self)
        self.main_container.setObjectName("MainContainer")
        self.main_container.setStyleSheet(DARK_STYLE)
        self.main_container.setMouseTracking(True)
        self.setCentralWidget(self.main_container)

        main_layout = QVBoxLayout(self.main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Custom Titlebar
        self.title_bar = QWidget()
        self.title_bar.setObjectName("TitleBar")
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(10, 6, 8, 6)
        title_layout.setSpacing(6)

        title_label = QLabel("✨ AI Work Companion · Guide Builder")
        title_label.setObjectName("AppTitle")

        # Opacity Slider & Label
        opacity_icon = QLabel("👁️")
        opacity_icon.setToolTip("Adjust Window Transparency")

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setFixedWidth(65)
        self.opacity_slider.setToolTip("Window Opacity / Transparency (30% - 100%)")
        initial_opacity = 100
        self.opacity_slider.setValue(initial_opacity)
        self.setWindowOpacity(initial_opacity / 100.0)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)

        self.opacity_label = QLabel(f"{initial_opacity}%")
        self.opacity_label.setStyleSheet("font-size: 10px; color: #94a3b8; min-width: 28px;")

        self.collapse_btn = QPushButton("🔽 Collapse")
        self.collapse_btn.setObjectName("TitleButton")
        self.collapse_btn.setToolTip("Collapse / Expand")
        self.collapse_btn.clicked.connect(self.toggle_collapse)

        self.close_btn = QPushButton("✖ Close")
        self.close_btn.setObjectName("TitleButton")
        self.close_btn.setObjectName("CloseButton")
        self.close_btn.setToolTip("Close Companion")
        self.close_btn.clicked.connect(self.close)

        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(opacity_icon)
        title_layout.addWidget(self.opacity_slider)
        title_layout.addWidget(self.opacity_label)
        title_layout.addWidget(self.collapse_btn)
        title_layout.addWidget(self.close_btn)

        main_layout.addWidget(self.title_bar)

        # Content Area Widget (allows collapsing)
        self.content_area = QWidget()
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        # 2. Provider & Model Bar
        provider_panel = QWidget()
        provider_panel.setObjectName("ControlPanel")
        # 2. Main Controls Bar (Source & Selected Model Status - Always Visible)
        visible_controls = QWidget()
        visible_layout = QVBoxLayout(visible_controls)
        visible_layout.setContentsMargins(0, 0, 0, 0)
        visible_layout.setSpacing(4)

        # Row A: Source Selection
        source_row = QHBoxLayout()
        source_row.setSpacing(6)

        source_label = QLabel("Source:")
        source_label.setStyleSheet("font-size: 11px; color: #94a3b8;")

        self.source_combo = QComboBox()
        self.source_combo.setMinimumWidth(150)
        self.source_combo.setMaxVisibleItems(15)
        self.source_combo.setToolTip("Select target window or screen monitor to inspect")
        self.source_combo.currentIndexChanged.connect(self._on_source_selected)

        self.add_source_btn = QPushButton("+ Add")
        self.add_source_btn.setObjectName("SecondaryButton")
        self.add_source_btn.setToolTip("Add the selected source to this multi-source capture")
        self.add_source_btn.clicked.connect(self._add_selected_source)

        self.clear_sources_btn = QPushButton("Clear")
        self.clear_sources_btn.setObjectName("SecondaryButton")
        self.clear_sources_btn.setToolTip("Use only the current source")
        self.clear_sources_btn.clicked.connect(self._clear_selected_sources)

        self.refresh_sources_btn = QPushButton("↻ Refresh")
        self.refresh_sources_btn.setObjectName("SecondaryButton")
        self.refresh_sources_btn.setToolTip("Refresh list of open windows and monitors")
        self.refresh_sources_btn.clicked.connect(self._refresh_sources)

        self.full_screen_btn = QPushButton("🖥️ Full Screen")
        self.full_screen_btn.setObjectName("SecondaryButton")
        self.full_screen_btn.setToolTip("Use the primary monitor as the capture target")
        self.full_screen_btn.clicked.connect(self._select_full_screen)

        self.picker_btn = QPushButton("📐 Select Area")
        self.picker_btn.setObjectName("SecondaryButton")
        self.picker_btn.setToolTip("Click & drag across screen to capture a specific area")
        self.picker_btn.clicked.connect(self._start_picker_overlay)

        self.watchdog_btn = QPushButton("🛡️ Watchdog")
        self.watchdog_btn.setObjectName("SecondaryButton")
        self.watchdog_btn.setCheckable(True)
        self.watchdog_btn.setToolTip("Toggle Sentinel background screen monitor (Passive Watchdog)")
        self.watchdog_btn.clicked.connect(self.toggle_watchdog)

        self.sentinel_badge = QLabel("🛡️ Off")
        self.sentinel_badge.setStyleSheet("font-size: 10px; color: #64748b; font-weight: bold;")
        self.sentinel_badge.setToolTip("Click '📊 Log' to view detailed Sentinel evaluation history")

        self.sentinel_log_btn = QPushButton("📊 Log")
        self.sentinel_log_btn.setObjectName("SecondaryButton")
        self.sentinel_log_btn.setToolTip("View Sentinel Evaluation Log & Performance Metrics")
        self.sentinel_log_btn.clicked.connect(self.show_sentinel_log)

        source_row.addWidget(source_label)
        source_row.addWidget(self.source_combo, 1)
        source_row.addWidget(self.refresh_sources_btn)

        self.selected_sources_lbl = QLabel("Capture source: current selection")
        self.selected_sources_lbl.setStyleSheet("font-size: 10px; color: #38bdf8;")
        self.selected_sources_lbl.setWordWrap(True)

        self.capture_status_lbl = QLabel()
        self.capture_status_lbl.setObjectName("CaptureStatus")
        self.capture_status_lbl.setWordWrap(True)

        preview_row = QHBoxLayout()
        preview_row.setSpacing(6)
        self.preview_btn = QPushButton("👁️ Preview")
        self.preview_btn.setObjectName("SecondaryButton")
        self.preview_btn.setToolTip("Preview exactly what will be captured")
        self.preview_btn.clicked.connect(self.preview_capture)
        self.add_capture_btn = QPushButton("＋ Add Capture")
        self.add_capture_btn.setObjectName("ActionButton")
        self.add_capture_btn.setToolTip("Capture the selected source and add it to your guide steps without sending it to AI")
        self.add_capture_btn.clicked.connect(self.capture_to_guide)
        preview_row.addWidget(self.preview_btn)
        preview_row.addWidget(self.add_capture_btn)
        preview_row.addWidget(self.selected_sources_lbl, 1)

        # Capture mode is explicit and separate from choosing a window/monitor.
        capture_mode_row = QHBoxLayout()
        capture_mode_row.setSpacing(6)
        capture_mode_label = QLabel("Capture:")
        capture_mode_label.setStyleSheet("font-size: 11px; color: #94a3b8;")
        capture_mode_row.addWidget(capture_mode_label)
        capture_mode_row.addWidget(self.full_screen_btn)
        capture_mode_row.addWidget(self.picker_btn)
        capture_mode_row.addStretch()

        production_row = QHBoxLayout()
        production_label = QLabel("Produce:")
        production_label.setStyleSheet("font-size: 11px; color: #7dd3fc; font-weight: bold;")
        self.guide_type_combo = QComboBox()
        self.guide_type_combo.addItems([
            "Work Instruction", "SOP", "Teaching Guide", "Study Guide", "Quick Reference",
        ])
        self.guide_type_combo.setToolTip("Choose the production to create from the current snapshot")
        self.guide_type_combo.currentTextChanged.connect(self._on_guide_type_changed)
        production_row.addWidget(production_label)
        production_row.addWidget(self.guide_type_combo)
        production_row.addStretch()

        # Row B: Selected Model Status & Options Toggle
        model_row = QHBoxLayout()
        model_row.setSpacing(6)

        model_label = QLabel("Model:")
        model_label.setStyleSheet("font-size: 11px; color: #94a3b8;")

        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(150)
        self.model_combo.setMaxVisibleItems(15)
        self.model_combo.setToolTip("Active model for visual reasoning and chat")

        self.model_search_input = QLineEdit()
        self.model_search_input.setObjectName("PromptInput")
        self.model_search_input.setPlaceholderText("Find model…")
        self.model_search_input.setClearButtonEnabled(True)
        self.model_search_input.setToolTip("Filter the model selector by name, provider, or capability")
        self.model_search_input.textChanged.connect(self._filter_models)

        self.adv_toggle_btn = QPushButton("⚙️ Options ▾")
        self.adv_toggle_btn.setObjectName("AdvToggleBtn")
        self.adv_toggle_btn.setToolTip("Show or hide advanced provider & filter options")
        self.adv_toggle_btn.clicked.connect(self._toggle_advanced_panel)

        model_row.addWidget(model_label)
        model_row.addWidget(self.model_search_input, 1)
        model_row.addWidget(self.model_combo, 1)
        model_row.addWidget(self.adv_toggle_btn)

        # Sentinel is an advanced, optional background monitor—not part of the
        # normal capture-and-guide workflow.
        watchdog_row = QHBoxLayout()
        watchdog_row.setSpacing(6)

        watchdog_label = QLabel("Sentinel:")
        watchdog_label.setStyleSheet("font-size: 11px; color: #94a3b8;")

        watchdog_row.addWidget(watchdog_label)
        watchdog_row.addWidget(self.watchdog_btn)
        watchdog_row.addWidget(self.sentinel_badge)
        watchdog_row.addStretch()
        watchdog_row.addWidget(self.sentinel_log_btn)

        visible_layout.addLayout(source_row)
        visible_layout.addLayout(preview_row)
        visible_layout.addWidget(self.capture_status_lbl)
        visible_layout.addLayout(capture_mode_row)
        visible_layout.addLayout(production_row)
        content_layout.addWidget(visible_controls)

        # 3. Advanced Options Panel (Collapsed by Default)
        self.adv_panel = QWidget()
        self.adv_panel.setObjectName("AdvPanel")
        adv_layout = QVBoxLayout(self.adv_panel)
        adv_layout.setContentsMargins(6, 6, 6, 6)
        adv_layout.setSpacing(6)

        # Provider Selector Row
        provider_row = QHBoxLayout()
        provider_row.setSpacing(6)

        provider_label = QLabel("Provider:")
        provider_label.setStyleSheet("font-size: 11px; color: #94a3b8;")

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(["LM Studio (Local)", "OpenRouter (Hosted)"])
        self.provider_combo.setToolTip("Switch between local LM Studio server and hosted OpenRouter API")
        active_prov = self.config.get("active_provider", "lmstudio")
        self.provider_combo.setCurrentIndex(1 if active_prov == "openrouter" else 0)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)

        self.privacy_badge = QLabel()
        self._update_privacy_badge()

        provider_row.addWidget(provider_label)
        provider_row.addWidget(self.provider_combo)
        provider_row.addWidget(self.privacy_badge)
        provider_row.addStretch()

        # Model Filter Row (model search lives beside the selector above)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(4)

        filter_label = QLabel("Model filters:")
        filter_label.setStyleSheet("font-size: 11px; color: #94a3b8;")

        self.vision_filter_btn = QPushButton("👁️ Vision")
        self.vision_filter_btn.setObjectName("SecondaryButton")
        self.vision_filter_btn.setCheckable(True)
        self.vision_filter_btn.setChecked(True)
        self.vision_filter_btn.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #059669;")
        self.vision_filter_btn.setToolTip("Filter only models that support vision / image input")
        self.vision_filter_btn.toggled.connect(self._on_vision_filter_toggled)

        self.free_filter_btn = QPushButton("⚡ Free")
        self.free_filter_btn.setObjectName("SecondaryButton")
        self.free_filter_btn.setCheckable(True)
        self.free_filter_btn.setToolTip("Filter only free models (:free)")
        self.free_filter_btn.toggled.connect(self._on_free_filter_toggled)

        self.refresh_models_btn = QPushButton("↻ Refresh")
        self.refresh_models_btn.setObjectName("SecondaryButton")
        self.refresh_models_btn.setToolTip("Refresh models from server")
        self.refresh_models_btn.clicked.connect(self.fetch_models)

        filter_row.addWidget(filter_label)
        filter_row.addWidget(self.vision_filter_btn)
        filter_row.addWidget(self.free_filter_btn)
        filter_row.addStretch()
        filter_row.addWidget(self.refresh_models_btn)

        adv_layout.addLayout(provider_row)
        adv_layout.addLayout(filter_row)
        adv_layout.addLayout(model_row)
        adv_layout.addLayout(watchdog_row)

        self.adv_panel.setVisible(False)  # Collapsed by default
        content_layout.addWidget(self.adv_panel)

        self.preview_panel = QFrame()
        self.preview_panel.setObjectName("PreviewPanel")
        self.preview_panel.setMinimumHeight(120)
        self.preview_panel.setMaximumHeight(180)
        self.preview_layout = QHBoxLayout(self.preview_panel)
        self.preview_layout.setContentsMargins(4, 4, 4, 4)
        self.preview_layout.setSpacing(6)
        self.preview_hint = QLabel("Preview will appear here")
        self.preview_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        self.preview_layout.addWidget(self.preview_hint)
        content_layout.addWidget(self.preview_panel)

        # 4. Chat Stream Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.chat_stream = QWidget()
        self.chat_stream.setObjectName("ChatStream")
        self.chat_layout = QVBoxLayout(self.chat_stream)
        self.chat_layout.setContentsMargins(4, 4, 4, 4)
        self.chat_layout.setSpacing(8)
        self.chat_layout.addStretch()

        self.scroll_area.setWidget(self.chat_stream)
        content_layout.addWidget(self.scroll_area, 1)

        # Current snapshot controls
        self.badge_container = QWidget()
        self.badge_layout = QHBoxLayout(self.badge_container)
        self.badge_layout.setContentsMargins(4, 0, 4, 0)
        self.badge_container.hide()
        content_layout.addWidget(self.badge_container)

        # 6. Input Area
        input_panel = QWidget()
        input_panel.setObjectName("InputPanel")
        input_layout = QVBoxLayout(input_panel)
        input_layout.setContentsMargins(4, 4, 4, 4)
        input_layout.setSpacing(6)

        prompt_row = QHBoxLayout()
        self.prompt_input = PromptTextEdit()
        self.prompt_input.setObjectName("PromptInput")
        self.prompt_input.setPlaceholderText("What should this production explain?")
        self.prompt_input.return_pressed.connect(self.send_query)
        self.prompt_input.escape_pressed.connect(self._handle_escape_key)

        self.send_btn = QPushButton("✦ Ask AI")
        self.send_btn.setObjectName("ActionButton")
        self.send_btn.setToolTip("Send prompt to companion (Enter to send, Shift+Enter for newline)")
        self.send_btn.clicked.connect(self.send_query)

        prompt_row.addWidget(self.prompt_input, 1)
        prompt_row.addWidget(self.send_btn)
        input_layout.addLayout(prompt_row)

        # Action Buttons & Resize Grip Row
        actions_row = QHBoxLayout()
        actions_row.setSpacing(6)

        self.save_screen_btn = QPushButton("💾 Save PNG")
        self.save_screen_btn.setObjectName("SecondaryButton")
        self.save_screen_btn.setToolTip("Capture the selected target and save a PNG file only")
        self.save_screen_btn.clicked.connect(self.capture_and_save_screen)

        self.clear_chat_btn = QPushButton("🗑️ Clear Chat")
        self.clear_chat_btn.setObjectName("SecondaryButton")
        self.clear_chat_btn.setToolTip("Clear the conversation and any unsent screenshot attachments")
        self.clear_chat_btn.clicked.connect(self.clear_chat)

        self.size_grip = QSizeGrip(self)

        actions_row.addWidget(self.save_screen_btn, 1)
        actions_row.addWidget(self.clear_chat_btn, 1)
        actions_row.addStretch()
        actions_row.addWidget(self.size_grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        input_layout.addLayout(actions_row)

        content_layout.addWidget(input_panel)
        main_layout.addWidget(self.content_area, 1)

    def _toggle_advanced_panel(self):
        is_visible = not self.adv_panel.isVisible()
        self.adv_panel.setVisible(is_visible)
        self.adv_toggle_btn.setText("⚙️ Options ▴" if is_visible else "⚙️ Options ▾")

    def _on_chip_clicked(self, prompt: str):
        self.prompt_input.setText(prompt)
        self.send_query()

    def _on_guide_type_changed(self, guide_type: str):
        self.current_guide_type = guide_type

    @staticmethod
    def _guide_draft_instruction(guide_type: str) -> str:
        sections = {
            "Work Instruction": "Purpose, prerequisites, numbered steps, expected result after each step, warnings, and troubleshooting.",
            "SOP": "Purpose, scope, prerequisites, roles, numbered procedure, quality checks, exceptions, and revision notes.",
            "Teaching Guide": "Audience, learning objectives, materials, instructor demonstration, guided practice, independent practice, and assessment.",
            "Study Guide": "Learning goals, key concepts, annotated examples, key terms, review questions, and a short self-check.",
            "Quick Reference": "A short purpose statement, concise numbered actions, key warnings, and a final verification checklist.",
        }
        structure = sections.get(guide_type, sections["Work Instruction"])
        return (
            f"Create a polished {guide_type} from the user's request and attached screenshots. "
            f"Use this structure: {structure} "
            "Treat each screenshot as evidence for a step. Do not invent clicks, fields, values, or results that are not visible or stated. "
            "Use clear Markdown headings and numbered steps; refer to screenshots as [Image 1], [Image 2], and so on where helpful."
        )

    def _handle_escape_key(self):
        if hasattr(self, 'picker_overlay') and self.picker_overlay and self.picker_overlay.isVisible():
            self._cancel_picker()
        elif hasattr(self, 'prompt_input') and self.prompt_input.text():
            self.prompt_input.clear()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._handle_escape_key()
            event.accept()
        else:
            super().keyPressEvent(event)

    def add_system_welcome(self):
        msg = (
            "Choose a source, then use **Preview** to check it or **Add Capture** to collect guide steps. "
            "Nothing is sent to AI until you write a request and choose **Ask AI**."
        )
        widget = ChatMessageWidget("assistant", msg)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, widget)

    # Window Drag, Resize & Geometry Persistence
    def _get_resize_edges(self, pos: QPoint):
        edges = set()
        rect = self.rect()
        m = self.RESIZE_MARGIN
        if pos.x() <= m:
            edges.add("left")
        elif pos.x() >= rect.width() - m:
            edges.add("right")
        if pos.y() <= m:
            edges.add("top")
        elif pos.y() >= rect.height() - m:
            edges.add("bottom")
        return edges

    def _update_cursor_for_position(self, pos: QPoint):
        edges = self._get_resize_edges(pos)
        if ("left" in edges and "top" in edges) or ("right" in edges and "bottom" in edges):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif ("right" in edges and "top" in edges) or ("left" in edges and "bottom" in edges):
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        elif "left" in edges or "right" in edges:
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        elif "top" in edges or "bottom" in edges:
            self.setCursor(Qt.CursorShape.SizeVerCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            edges = self._get_resize_edges(pos)
            if edges and not self.is_collapsed:
                self.is_resizing = True
                self.resize_edges = edges
                self.resize_start_pos = event.globalPosition().toPoint()
                self.resize_start_geometry = self.geometry()
                event.accept()
                return
            elif pos.y() < 40:
                self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if self.is_resizing and not self.is_collapsed:
            global_pos = event.globalPosition().toPoint()
            delta = global_pos - self.resize_start_pos
            geo = QRect(self.resize_start_geometry)

            min_w, min_h = self.minimumWidth(), self.minimumHeight()

            if "right" in self.resize_edges:
                geo.setWidth(max(min_w, geo.width() + delta.x()))
            elif "left" in self.resize_edges:
                new_w = max(min_w, geo.width() - delta.x())
                geo.setX(geo.right() - new_w)

            if "bottom" in self.resize_edges:
                geo.setHeight(max(min_h, geo.height() + delta.y()))
            elif "top" in self.resize_edges:
                new_h = max(min_h, geo.height() - delta.y())
                geo.setY(geo.bottom() - new_h)

            self.setGeometry(geo)
            event.accept()
        elif event.buttons() == Qt.MouseButton.LeftButton and not self.drag_position.isNull():
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
        else:
            if not self.is_collapsed:
                self._update_cursor_for_position(pos)

    def mouseReleaseEvent(self, event):
        self.is_resizing = False
        self.drag_position = QPoint()
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._save_geometry()

    def _save_geometry(self):
        geo = self.geometry()
        self.config.set("window_geometry", {
            "width": geo.width(),
            "height": geo.height(),
            "x": geo.x(),
            "y": geo.y()
        })

    def _load_saved_geometry(self):
        geo = self.config.get("window_geometry")
        if geo:
            w = max(460, geo.get("width", 460))
            h = max(720, geo.get("height", 720))
            self.setGeometry(geo.get("x", 100), geo.get("y", 100), w, h)

    def _on_opacity_changed(self, value: int):
        opacity = max(0.3, min(1.0, value / 100.0))
        self.setWindowOpacity(opacity)
        self.opacity_label.setText(f"{value}%")
        self.config.set("window_opacity", value)

    def toggle_collapse(self):
        self.is_collapsed = not self.is_collapsed
        if self.is_collapsed:
            self.content_area.hide()
            self.setFixedHeight(40)
            self.collapse_btn.setText("□")
        else:
            self.setMinimumSize(460, 720)
            self.setMaximumSize(16777215, 16777215)
            self.content_area.show()
            geo = self.config.get("window_geometry", {})
            target_w = max(460, geo.get("width", 460))
            target_h = max(720, geo.get("height", 720))
            self.resize(target_w, target_h)
            self.collapse_btn.setText("─")

    # Sources & Target Selection
    def _refresh_sources(self):
        previous_key = self._target_key(self.active_target) if self.active_target else None
        self.source_combo.blockSignals(True)
        self.source_combo.clear()
        self.selected_targets.clear()
        self.preview_pixmaps.clear()
        self.last_capture_targets.clear()
        self._clear_preview()

        screens = self.platform.list_screens()
        windows = self.platform.list_windows()

        for s in screens:
            self.source_combo.addItem(f"🖥️ {s.name}", s)
        for w in windows:
            self.source_combo.addItem(f"🪟 {w.name}", w)

        self.source_combo.blockSignals(False)
        restored_index = -1
        if previous_key:
            for index in range(self.source_combo.count()):
                target = self.source_combo.itemData(index)
                if isinstance(target, SourceTarget) and self._target_key(target) == previous_key:
                    restored_index = index
                    break
        self._on_source_selected(restored_index if restored_index >= 0 else 0)
        if restored_index >= 0:
            self.source_combo.setCurrentIndex(restored_index)

    def _on_source_selected(self, index: int):
        target = self.source_combo.itemData(index)
        if isinstance(target, SourceTarget):
            self.active_target = target
            self._update_selected_sources_label()
            self._update_capture_status(target)

    def _update_capture_status(self, target: Optional[SourceTarget] = None, notice: str = "") -> None:
        """Keep capture limitations visible before the user presses a button."""
        target = target or self.active_target
        if notice:
            self.capture_status_lbl.setText(f"ⓘ {notice}")
            self.capture_status_lbl.setStyleSheet("color: #fbbf24; font-size: 10px;")
            return
        if self.platform.name != "linux-wayland":
            self.capture_status_lbl.clear()
            return
        # Keep this area quiet during normal work. It is reserved for a
        # successful capture notice or an actionable failure.
        self.capture_status_lbl.clear()

    def _capture_targets(self) -> list[SourceTarget]:
        """Return the committed multi-source selection, or the current source."""
        if self.selected_targets:
            return list(self.selected_targets)
        return [self.active_target] if self.active_target else []

    @staticmethod
    def _target_key(target: SourceTarget) -> tuple[str, str]:
        return target.target_type, target.target_id

    def _add_selected_source(self) -> None:
        target = self.active_target
        if not target:
            return

        if not any(self._target_key(item) == self._target_key(target) for item in self.selected_targets):
            self.selected_targets.append(target)
        self._update_selected_sources_label()

    def _clear_selected_sources(self) -> None:
        self.selected_targets.clear()
        self._update_selected_sources_label()

    def _update_selected_sources_label(self) -> None:
        if not self.selected_targets:
            self.selected_sources_lbl.setText("Capture source: current selection")
            self.clear_sources_btn.setEnabled(False)
            return
        names = [target.name for target in self.selected_targets]
        self.selected_sources_lbl.setText(f"Capture set ({len(names)}): " + "  +  ".join(names))
        self.clear_sources_btn.setEnabled(True)

    def _clear_preview(self) -> None:
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.preview_hint = QLabel("Preview will appear here")
        self.preview_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_hint.setStyleSheet("color: #64748b; font-size: 11px;")
        self.preview_layout.addWidget(self.preview_hint)

    def _show_preview(self, pixmaps: list[QPixmap], targets: list[SourceTarget]) -> None:
        self.preview_pixmaps = list(pixmaps)
        self._clear_preview()
        if not pixmaps:
            self.preview_hint.setText("Capture preview unavailable")
            self.preview_hint.show()
            return

        self.preview_hint.hide()
        for target, pixmap in zip(targets, pixmaps):
            if not pixmap or pixmap.isNull():
                continue
            card = QLabel()
            card.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card.setToolTip(target.name)
            card.setPixmap(pixmap.scaled(
                220, 135,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))
            card.setStyleSheet("border: 1px solid #0284c7; border-radius: 4px;")
            self.preview_layout.addWidget(card)

        self.preview_layout.addStretch()

    @staticmethod
    def _compose_window_captures(captures: list[tuple[SourceTarget, QPixmap]]) -> Optional[QPixmap]:
        """Compose selected window images in their original desktop positions."""
        valid = [
            (target, pixmap)
            for target, pixmap in captures
            if target.rect and target.rect.isValid() and pixmap and not pixmap.isNull()
        ]
        if not valid:
            return None

        union = QRect()
        for target, _ in valid:
            union = union.united(target.rect)

        # Capture sizes are physical pixels while window rectangles are logical
        # desktop coordinates. Use the first image's scale for the composite.
        first_target, first_pixmap = valid[0]
        scale_x = first_pixmap.width() / max(1, first_target.rect.width())
        scale_y = first_pixmap.height() / max(1, first_target.rect.height())
        scale = max(0.01, min(scale_x, scale_y))

        canvas_width = max(1, int(round(union.width() * scale)))
        canvas_height = max(1, int(round(union.height() * scale)))
        canvas = QPixmap(canvas_width, canvas_height)
        canvas.fill(Qt.GlobalColor.transparent)

        painter = QPainter(canvas)
        try:
            for target, pixmap in valid:
                rect = target.rect
                dest = QRect(
                    int(round((rect.x() - union.x()) * scale)),
                    int(round((rect.y() - union.y()) * scale)),
                    # Toplevel export may omit compositor decorations. Keep
                    # the clean client pixels at their native size instead of
                    # stretching them to the Hyprland window geometry.
                    pixmap.width(),
                    pixmap.height(),
                )
                if pixmap.size() == dest.size():
                    painter.drawPixmap(dest.topLeft(), pixmap)
                else:
                    painter.drawPixmap(
                        dest,
                        pixmap,
                        pixmap.rect(),
                    )
        finally:
            painter.end()

        return canvas

    def _capture_targets_now(self, targets: list[SourceTarget]) -> list[QPixmap]:
        """Capture targets while the companion is hidden, restoring prior focus."""
        if not targets:
            return []

        previous_target = self.platform.active_window()
        captures: list[tuple[SourceTarget, QPixmap]] = []
        self.last_capture_errors.clear()
        self.hide()
        QApplication.processEvents()
        try:
            # Capture each target separately. The Wayland backend prefers clean
            # client pixels when its helper is present and otherwise captures
            # the visible client region through grim.
            for target in targets:
                pixmap = self.platform.capture_target(target)
                if pixmap and not pixmap.isNull():
                    captures.append((target, pixmap))
                    notice = getattr(self.platform, "last_capture_notice", "")
                    if notice:
                        self._update_capture_status(target, notice)
                else:
                    detail = getattr(self.platform, "last_capture_error", "")
                    if detail:
                        self.last_capture_errors.append(detail)
        finally:
            # Hyprland's toplevel export does not change focus. Avoid even a
            # redundant focus dispatch so inactive-workspace capture can never
            # pull the user away from the workspace they are using.
            if previous_target and self.platform.name != "linux-wayland":
                self.platform.activate_window(previous_target)
            self.show()
            self.raise_()
            self.activateWindow()
            QApplication.processEvents()
        if len(targets) > 1 and all(target.target_type == "window" for target in targets):
            composite = self._compose_window_captures(captures)
            if composite and not composite.isNull():
                union = QRect()
                for target, _ in captures:
                    if target.rect:
                        union = union.united(target.rect)
                self.last_capture_targets = [SourceTarget(
                    target_type="window_group",
                    target_id="+".join(target.target_id for target in targets),
                    name=f"Selected Windows ({len(captures)})",
                    rect=union if union.isValid() else None,
                )]
                return [composite]

        self.last_capture_targets = [target for target, _ in captures]
        return [pixmap for _, pixmap in captures]

    def preview_capture(self) -> None:
        targets = self._capture_targets()
        if not targets:
            self._show_capture_error("Select a screen or window before previewing.")
            return
        self.preview_btn.setEnabled(False)
        try:
            pixmaps = self._capture_targets_now(targets)
            if pixmaps:
                self._show_preview(pixmaps, self.last_capture_targets or targets)
            else:
                self._show_preview([], targets)
                self._show_capture_error()
        finally:
            self.preview_btn.setEnabled(True)

    def _select_full_screen(self):
        """Select the first listed monitor as the explicit full-screen target."""
        self.selected_targets.clear()
        for index in range(self.source_combo.count()):
            target = self.source_combo.itemData(index)
            if isinstance(target, SourceTarget) and target.target_type == "screen":
                self.source_combo.setCurrentIndex(index)
                self.active_target = target
                return

        # Sources can change while the app is open; refresh once and retry.
        self._refresh_sources()
        for index in range(self.source_combo.count()):
            target = self.source_combo.itemData(index)
            if isinstance(target, SourceTarget) and target.target_type == "screen":
                self.source_combo.setCurrentIndex(index)
                self.active_target = target
                return

    def _start_picker_overlay(self):
        self.overlay = PickerOverlay()
        self.overlay.target_selected.connect(self._on_picker_target_selected)
        self.overlay.show_overlay()

    def _on_picker_target_selected(self, target: SourceTarget):
        self.selected_targets.clear()
        self.active_target = target
        # Add temporary entry to combo
        self.source_combo.blockSignals(True)
        self.source_combo.insertItem(0, f"📐 {target.name}", target)
        self.source_combo.setCurrentIndex(0)
        self.source_combo.blockSignals(False)

    # Provider & Model Management
    def _on_provider_changed(self, index: int):
        new_provider = "openrouter" if index == 1 else "lmstudio"
        
        if new_provider == "openrouter":
            # Check privacy acceptance
            saved_key = self.config.get("openrouter_key", "")
            dialog = OpenRouterPrivacyDialog(current_key=saved_key, parent=self)
            dialog.accepted_key.connect(self._on_openrouter_accepted)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                # Revert to LM Studio
                self.provider_combo.blockSignals(True)
                self.provider_combo.setCurrentIndex(0)
                self.provider_combo.blockSignals(False)
                return

        self.config.set("active_provider", new_provider)
        self._update_privacy_badge()
        self.fetch_models()

    def _on_openrouter_accepted(self, key: str):
        self.config.set("openrouter_key", key)
        self.config.set("openrouter_privacy_accepted", True)

    def _update_privacy_badge(self):
        provider = self.config.get("active_provider", "lmstudio")
        if provider == "openrouter":
            self.privacy_badge.setText("OPENROUTER 🌐")
            self.privacy_badge.setObjectName("PrivacyBadgeOnline")
        else:
            self.privacy_badge.setText("LOCAL 🔒")
            self.privacy_badge.setObjectName("PrivacyBadgeLocal")
        self.privacy_badge.setStyle(self.privacy_badge.style())

    def fetch_models(self):
        provider = self.config.get("active_provider", "lmstudio")
        base_url = self.config.get("openrouter_url") if provider == "openrouter" else self.config.get("lmstudio_url")
        api_key = self.config.get("openrouter_key") if provider == "openrouter" else ""

        if self.model_fetch_worker and self.model_fetch_worker.isRunning():
            self.model_fetch_worker.quit()
            self.model_fetch_worker.wait(1000)

        self.model_combo.clear()
        self.model_combo.addItem("Loading models...")
        
        self.model_fetch_worker = ModelFetchWorker(provider, base_url, api_key)
        self.model_fetch_worker.models_fetched.connect(self._on_models_fetched)
        self.model_fetch_worker.start()

    def _on_models_fetched(self, models: list, error: str):
        if error:
            self.all_models = []
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItem("Default / Fallback")
            self.model_combo.blockSignals(False)
            print(f"Model fetch note: {error}")
            return

        self.all_models = models or []
        self._filter_models()

    def _on_vision_filter_toggled(self, checked: bool):
        if checked:
            self.vision_filter_btn.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #059669;")
        else:
            self.vision_filter_btn.setStyleSheet("")
        self._filter_models()

    def _on_free_filter_toggled(self, checked: bool):
        if checked:
            self.free_filter_btn.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #059669;")
        else:
            self.free_filter_btn.setStyleSheet("")
        self._filter_models()

    def _filter_models(self):
        query = self.model_search_input.text().strip().lower()
        free_only = self.free_filter_btn.isChecked()
        vision_only = self.vision_filter_btn.isChecked()

        if not self.all_models:
            return

        tokens = query.split()
        filtered = []

        for m in self.all_models:
            if isinstance(m, dict):
                m_id = m.get("id", "")
                is_vis = m.get("is_vision", True)
                is_fr = m.get("is_free", False)
            else:
                m_id = str(m)
                m_lower = m_id.lower()
                is_vis = any(kw in m_lower for kw in ["vision", "-vl", "llava", "pixtral", "minicpm", "gemini", "claude-3", "gpt-4o", "gemma-4", "multimodal"])
                is_fr = ":free" in m_lower or "-free" in m_lower

            m_id_lower = m_id.lower()

            if vision_only and not is_vis:
                continue

            if free_only and not is_fr and not ("free" in m_id_lower or ":free" in m_id_lower):
                continue

            if tokens:
                searchable = m_id_lower
                if is_vis:
                    searchable += " vision image multimodal"
                if is_fr:
                    searchable += " free"
                if not all(tok in searchable for tok in tokens):
                    continue

            filtered.append(m_id)

        current_selected = self.model_combo.currentText()

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        if filtered:
            for m in filtered:
                self.model_combo.addItem(m)
            # Try restoring previously selected model
            idx = self.model_combo.findText(current_selected)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                provider = self.config.get("active_provider", "lmstudio")
                saved_m = self.config.get(f"{provider}_model", "")
                idx_saved = self.model_combo.findText(saved_m)
                if idx_saved >= 0:
                    self.model_combo.setCurrentIndex(idx_saved)
                else:
                    self.model_combo.setCurrentIndex(0)
        else:
            criteria = []
            if query:
                criteria.append(f"‘{query}’")
            if vision_only:
                criteria.append("Vision")
            if free_only:
                criteria.append("Free")
            suffix = " + ".join(criteria) if criteria else "current filters"
            self.model_combo.addItem(f"No models match {suffix}")
        self.model_combo.blockSignals(False)

    # Screenshot & Query Execution
    def check_screen_now(self):
        if not self.active_target:
            self._refresh_sources()

        targets = self._capture_targets()
        if targets:
            pixmaps = self._capture_targets_now(targets)
            if pixmaps:
                self.attached_pixmaps.extend(pixmaps)
                self.attached_images_b64.extend(pixmap_to_b64(pixmap) for pixmap in pixmaps)
                self._show_attached_badge()
            else:
                self._show_capture_error()
                return

        else:
            self._show_capture_error("No capture target is available. Refresh the source list and select a screen or area.")
            return
        
        # If user has prompt typed, execute. Otherwise send default screen check
        prompt = self.prompt_input.text().strip()
        if not prompt:
            prompt = "Check the screen and provide guidance on what is visible."
        self.send_query_with_prompt(prompt)

    def capture_to_guide(self):
        """Capture only: queue evidence for editing or a later AI request."""
        if not self.active_target:
            self._refresh_sources()
        targets = self._capture_targets()
        if not targets:
            self._show_capture_error("No capture target is available. Refresh the source list and select a screen or area.")
            return
        pixmaps = self._capture_targets_now(targets)
        if not pixmaps:
            self._show_capture_error()
            return
        self.attached_pixmaps = [pixmaps[0]]
        self.attached_images_b64 = [pixmap_to_b64(pixmaps[0])]
        self._show_attached_badge()
        self.capture_status_lbl.setText("✓ Snapshot ready. Edit it below or ask AI when ready.")
        self.capture_status_lbl.setStyleSheet("color: #86efac; font-size: 10px;")

    def _save_pixmap_to_disk(self, pixmap: QPixmap) -> Optional[str]:
        if not pixmap or pixmap.isNull():
            return None
        try:
            self.capture_sequence += 1
            dir_str = self.config.get("captures_dir")
            if not dir_str:
                dir_str = str(self.config.storage.layout.captures)
            captures_dir = Path(dir_str)
            captures_dir.mkdir(parents=True, exist_ok=True)

            ts = time.strftime("%Y%m%d_%H%M%S")
            filename = f"capture_step_{self.capture_sequence:02d}_{ts}.png"
            filepath = captures_dir / filename

            if pixmap.save(str(filepath), "PNG"):
                msg = f"💾 **Step {self.capture_sequence} Saved**: `{filepath}`"
                asst_widget = ChatMessageWidget("assistant", msg)
                self.chat_layout.insertWidget(self.chat_layout.count() - 1, asst_widget)
                self.scroll_to_bottom()
                return str(filepath)
        except Exception as e:
            print(f"Error saving screenshot to disk: {e}")
        return None

    def capture_and_save_screen(self):
        if not self.active_target:
            self._refresh_sources()

        targets = self._capture_targets()
        if targets:
            pixmaps = self._capture_targets_now(targets)
            if pixmaps:
                for pixmap in pixmaps:
                    self._save_pixmap_to_disk(pixmap)
            else:
                self._show_capture_error()
        else:
            self._show_capture_error("No capture target is available. Refresh the source list and select a screen or area.")

    def capture_and_annotate(self):
        """Capture the selected sources and queue annotated images for the next chat turn."""
        if not self.active_target:
            self._refresh_sources()

        targets = self._capture_targets()
        if not targets:
            self._show_capture_error("No capture target is available. Refresh the source list and select a screen or area.")
            return

        pixmaps = self._capture_targets_now(targets)
        if not pixmaps:
            self._show_capture_error()
            return

        from capture.annotation_dialog import AnnotationDialog

        annotated: list[QPixmap] = []
        for pixmap in pixmaps:
            dialog = AnnotationDialog(pixmap, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                annotated.append(dialog.get_result_pixmap())
            else:
                annotated.append(pixmap)

        self.attached_pixmaps.extend(annotated)
        self.attached_images_b64.extend(pixmap_to_b64(pixmap) for pixmap in annotated)
        self._show_attached_badge()

    def _show_capture_error(self, detail: Optional[str] = None):
        if detail is None:
            if self.last_capture_errors:
                detail = self.last_capture_errors[-1]
            elif self.platform.name == "linux-wayland":
                detail = (
                    "Wayland did not provide a screenshot. On Hyprland or Sway, install `grim` "
                    "and make sure the companion is running in your desktop session."
                )
            else:
                detail = "The selected target could not be captured. Refresh the source list and try again."
        self.capture_status_lbl.setText(f"⚠ {detail}")
        self.capture_status_lbl.setStyleSheet("color: #fca5a5; font-size: 10px;")
        message = ChatMessageWidget("assistant", f"⚠️ **Screen capture failed**: {detail}")
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, message)
        self.scroll_to_bottom()

    def _show_attached_badge(self):
        # Clear existing badge items
        while self.badge_layout.count():
            item = self.badge_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if self.attached_pixmaps:
            badge = AttachedImageBadge(self.attached_pixmaps)
            badge.edit_requested.connect(self._open_annotation_editor)
            badge.remove_requested.connect(self._remove_attached_image)
            clear_btn = QPushButton("Clear Snapshot ✕")
            clear_btn.setObjectName("TitleButton")
            clear_btn.setStyleSheet("font-size: 10px; color: #ef4444; padding: 2px 6px;")
            clear_btn.setToolTip("Clear the current snapshot")
            clear_btn.clicked.connect(self._clear_attached_images)

            self.badge_layout.addWidget(badge, 1)
            self.badge_layout.addWidget(clear_btn)
            self.badge_container.show()
        else:
            self.badge_container.hide()

    def _open_annotation_editor(self, index: int = -1):
        if not self.attached_pixmaps or not (-len(self.attached_pixmaps) <= index < len(self.attached_pixmaps)):
            return
        from capture.annotation_dialog import AnnotationDialog
        target_pixmap = self.attached_pixmaps[index]
        dlg = AnnotationDialog(target_pixmap, self)
        if dlg.exec():
            res_pixmap = dlg.get_result_pixmap()
            self.attached_pixmaps[index] = res_pixmap
            b64_str = pixmap_to_b64(res_pixmap)
            self.attached_images_b64[index] = b64_str
            self._show_attached_badge()

    def _remove_attached_image(self, index: int):
        if 0 <= index < len(self.attached_pixmaps):
            del self.attached_pixmaps[index]
            del self.attached_images_b64[index]
            self._show_attached_badge()

    def _clear_attached_images(self):
        self.attached_pixmaps.clear()
        self.attached_images_b64.clear()
        self._show_attached_badge()

    def _hide_attached_badge(self):
        self.badge_container.hide()

    def send_query(self):
        prompt = self.prompt_input.text().strip()
        if not prompt:
            return
        self.send_query_with_prompt(prompt)

    def send_query_with_prompt(self, prompt: str):
        # Save active selected model
        provider = self.config.get("active_provider", "lmstudio")
        selected_model = self.model_combo.currentText()
        if selected_model and "Loading" not in selected_model:
            self.config.set(f"{provider}_model", selected_model)

        # Attach all accumulated images for this query. A guide type shapes the
        # draft without obscuring the user's original request in the chat.
        img_b64s = list(self.attached_images_b64)
        pixmaps = list(self.attached_pixmaps)
        self.last_sent_pixmaps = list(self.attached_pixmaps)
        guide_type = self.guide_type_combo.currentText()
        self.current_guide_type = guide_type
        self.pending_guide_type = guide_type
        self.last_guide_request = prompt
        draft_prompt = f"{self._guide_draft_instruction(guide_type)}\n\nUser request:\n{prompt}" if img_b64s else prompt

        # Update conversation session context
        self.conversation.add_user_message(draft_prompt, images_b64=img_b64s)

        # Clear input field & draft attachment state
        self.prompt_input.clear()
        self.attached_pixmaps.clear()
        self.attached_images_b64.clear()
        self._hide_attached_badge()

        # Add typing indicator widget for assistant response
        self.typing_widget = ChatMessageWidget("assistant", "Companion is analyzing your screen...")
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, self.typing_widget)
        self.scroll_to_bottom()

        # Disable inputs while inference runs and show loading indicator
        self.send_btn.setEnabled(False)
        self.add_capture_btn.setEnabled(False)
        self.send_btn.setText("⏳ Thinking...")
        self.add_capture_btn.setText("⏳ Working...")

        # Launch async inference worker
        base_url = self.config.get("openrouter_url") if provider == "openrouter" else self.config.get("lmstudio_url")
        api_key = self.config.get("openrouter_key") if provider == "openrouter" else ""
        model = selected_model if selected_model and "Loading" not in selected_model else "default"

        messages = self.conversation.get_openai_messages()

        self.inference_worker = InferenceWorker(provider, base_url, api_key, model, messages)
        self.inference_worker.response_ready.connect(self._on_ai_response)
        self.inference_worker.error_occurred.connect(self._on_ai_error)
        self.inference_worker.start()

    def _on_ai_response(self, text: str):
        from ai.conversation import parse_annotations
        from capture.annotation_utils import draw_annotation_on_pixmap

        # Remove typing widget
        if hasattr(self, 'typing_widget') and self.typing_widget:
            self.chat_layout.removeWidget(self.typing_widget)
            self.typing_widget.deleteLater()

        clean_text, annotations = parse_annotations(text)

        # Process annotations on last_sent_pixmaps if present
        annotated_pixmaps = [p.copy() for p in self.last_sent_pixmaps] if self.last_sent_pixmaps else []
        
        if annotations and annotated_pixmaps:
            for ann in annotations:
                img_idx = ann["image_index"] - 1
                if 0 <= img_idx < len(annotated_pixmaps):
                    annotated_pixmaps[img_idx] = draw_annotation_on_pixmap(
                        annotated_pixmaps[img_idx],
                        ann["type"],
                        ann["coords"],
                        is_normalized=ann.get("is_normalized", False)
                    )
            # Retain annotated pixmaps for export and future display
            self.last_sent_pixmaps = annotated_pixmaps

        # Add assistant response bubble with annotated thumbnails (or text only)
        # Every guide response retains its evidence images. Annotations merely
        # replace the relevant image; they must not decide whether screenshots
        # are available to the guide export.
        display_pixmaps = annotated_pixmaps or None
        asst_widget = ChatMessageWidget(
            "assistant", clean_text, pixmaps=display_pixmaps, guide_type=self.pending_guide_type, production_mode=True
        )
        asst_widget.export_requested.connect(self._handle_doc_export)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, asst_widget)
        self.scroll_to_bottom()

        self.conversation.add_assistant_message(clean_text)

        self.send_btn.setText("✦ Ask AI")
        self.add_capture_btn.setText("＋ Add Capture")
        self.send_btn.setEnabled(True)
        self.add_capture_btn.setEnabled(True)

    def _handle_doc_export(self, response_text: str, attached_pixmaps: list, guide_type: str = ""):
        try:
            # Strip raw <point> tags if present
            clean_response = re.sub(r'<point>.*?</point>', '', response_text).strip()
            if not clean_response:
                clean_response = response_text

            lines = [l.strip() for l in clean_response.splitlines() if l.strip()]
            candidate_title = lines[0] if lines else (guide_type or "Guide")

            # If response starts with a numbered step (e.g. "1. "), use user prompt text for title slug
            if re.match(r'^\d+[\.\)]', candidate_title) or len(candidate_title) < 5:
                candidate_title = self.last_guide_request or candidate_title

            res = DocumentExporter.export_finalized_doc(
                clean_response,
                attached_pixmaps,
                title=candidate_title,
                custom_export_dir=self.config.get("sop_export_dir") or str(self.config.storage.layout.exports)
            )

            html_url = f"file://{res['html_path']}"
            msg = f"📄 **Finalized Document Generated**:\n- HTML: [{Path(res['html_path']).name}]({html_url})\n- Markdown: `{res['md_path']}`"
            
            info_widget = ChatMessageWidget("assistant", msg)
            self.chat_layout.insertWidget(self.chat_layout.count() - 1, info_widget)
            self.scroll_to_bottom()
        except Exception as e:
            print(f"Export error: {e}")

    def _on_ai_error(self, err_msg: str):
        if hasattr(self, 'typing_widget') and self.typing_widget:
            self.chat_layout.removeWidget(self.typing_widget)
            self.typing_widget.deleteLater()

        err_widget = ChatMessageWidget("assistant", f"⚠️ {err_msg}")
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, err_widget)
        self.scroll_to_bottom()

        self.send_btn.setText("✦ Ask AI")
        self.add_capture_btn.setText("＋ Add Capture")
        self.send_btn.setEnabled(True)
        self.add_capture_btn.setEnabled(True)

    def clear_chat(self):
        self.conversation.clear()
        self.capture_sequence = 0
        self.attached_pixmaps.clear()
        self.attached_images_b64.clear()
        self._hide_attached_badge()
        # Remove all message widgets and old stretch elements
        while self.chat_layout.count() > 0:
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.chat_layout.addStretch()

    def scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def toggle_watchdog(self, checked: bool):
        if checked:
            if not self.sentinel_controller:
                self.sentinel_controller = SentinelController(self)
                self.sentinel_controller.worker.result_ready.connect(self._on_sentinel_result)
                self.sentinel_controller.worker.candidate_toast_triggered.connect(self._on_sentinel_toast_triggered)
                self.sentinel_controller.worker.processing_finished.connect(self._on_sentinel_finished)

            self._sentinel_busy = False
            self.sentinel_timer.start()
            self.watchdog_btn.setText("🛡️ Active")
            self.watchdog_btn.setStyleSheet("background-color: #1e3a8a; color: #60a5fa; border: 1px solid #3b82f6;")
            self.sentinel_badge.setText("🛡️ Active")
            self.sentinel_badge.setStyleSheet("font-size: 10px; color: #38bdf8; font-weight: bold;")
        else:
            self.sentinel_timer.stop()
            self._sentinel_busy = False
            self.watchdog_btn.setText("🛡️ Watchdog")
            self.watchdog_btn.setStyleSheet("")
            self.sentinel_badge.setText("🛡️ Off")
            self.sentinel_badge.setStyleSheet("font-size: 10px; color: #64748b; font-weight: bold;")

    def _on_sentinel_toast_triggered(self, candidate_record):
        if hasattr(self, 'active_toast') and self.active_toast:
            try:
                self.active_toast.close()
            except Exception:
                pass

        self.active_toast = SentinelToastWidget(candidate_record)
        self.active_toast.inspect_clicked.connect(self._on_toast_inspect)
        self.active_toast.mute_clicked.connect(self._on_toast_mute)
        self.active_toast.dismiss_clicked.connect(self._on_toast_dismiss)
        self.active_toast.show()
        self.active_toast.raise_()
        self.active_toast.activateWindow()

    def _on_toast_inspect(self, candidate_record):
        if candidate_record and self.sentinel_controller:
            self.sentinel_controller.worker.candidate_manager.suppress_fingerprint(candidate_record.fingerprint)

        if hasattr(self, 'active_toast') and self.active_toast:
            try:
                self.active_toast.close()
                self.active_toast = None
            except Exception:
                pass

        if candidate_record and candidate_record.crop_image:
            pixmap = QPixmap.fromImage(candidate_record.crop_image)
            if not pixmap.isNull():
                self.attached_pixmaps.append(pixmap)
                b64 = pixmap_to_b64(pixmap)
                self.attached_images_b64.append(b64)
                self._show_attached_badge()

        title_str = candidate_record.title if candidate_record else "Target Window"
        self.prompt_input.setText(f"Inspect detected error region on screen ({title_str}). What is wrong and how do I fix it?")
        if self.is_collapsed:
            self.toggle_collapse()
        self.activateWindow()
        self.raise_()

    def _on_toast_mute(self):
        if self.sentinel_controller:
            self.sentinel_controller.worker.candidate_manager.set_mute_5m()

    def _on_toast_dismiss(self, fingerprint: str):
        if self.sentinel_controller:
            self.sentinel_controller.worker.candidate_manager.suppress_fingerprint(fingerprint)

    def _on_sentinel_timer(self):
        if self._sentinel_busy:
            if self.sentinel_controller:
                self.sentinel_controller.worker.metrics.frames_dropped_busy += 1
            return

        if not self.active_target:
            return

        self._sentinel_busy = True
        pixmap = self.platform.capture_target(self.active_target)
        if pixmap and not pixmap.isNull():
            qimg_copy = pixmap.toImage().copy()
            if self.sentinel_controller:
                ctx = {
                    "timestamp": time.monotonic(),
                    "target_id": self.active_target.target_id,
                    "target_name": self.active_target.name
                }
                self.sentinel_controller.send_frame(qimg_copy, ctx)
        else:
            self._sentinel_busy = False

    def _on_sentinel_result(self, result, meta):
        # Record in sentinel logger & persistent file
        self.sentinel_logger.log_event(result, meta)

        state_str = result.state.name
        delta_pct = result.frame_delta_ratio * 100.0
        base_pct = result.baseline_delta_ratio * 100.0

        if result.state == SentinelState.CANDIDATE:
            badge_text = f"🛡️ CANDIDATE ({base_pct:.1f}%)"
            badge_color = "#f43f5e"  # Rose alert
            print(f"[WATCHDOG LOG] {result.message}")
        elif result.state == SentinelState.OBSERVING:
            badge_text = f"🛡️ Observing ({base_pct:.1f}%)"
            badge_color = "#fbbf24"  # Amber warning
        elif result.state == SentinelState.MOTION:
            badge_text = f"🛡️ Motion ({delta_pct:.1f}%)"
            badge_color = "#a855f7"  # Purple motion
        else:
            badge_text = f"🛡️ Stable"
            badge_color = "#38bdf8"  # Sky blue

        self.sentinel_badge.setText(badge_text)
        self.sentinel_badge.setStyleSheet(f"font-size: 10px; color: {badge_color}; font-weight: bold;")

    def show_sentinel_log(self):
        metrics = self.sentinel_controller.worker.metrics if self.sentinel_controller else None
        dlg = SentinelLogDialog(self.sentinel_logger, metrics, self)
        dlg.exec()

    def _on_sentinel_finished(self):
        self._sentinel_busy = False

    def closeEvent(self, event):
        if hasattr(self, 'sentinel_timer') and self.sentinel_timer:
            self.sentinel_timer.stop()
        if hasattr(self, 'sentinel_controller') and self.sentinel_controller:
            self.sentinel_controller.stop()
        if self.model_fetch_worker and self.model_fetch_worker.isRunning():
            self.model_fetch_worker.quit()
            self.model_fetch_worker.wait(1000)
        if self.inference_worker and self.inference_worker.isRunning():
            self.inference_worker.quit()
            self.inference_worker.wait(1000)
        super().closeEvent(event)

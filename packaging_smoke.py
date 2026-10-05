"""Offline release smoke check; never reads user config or captures the desktop."""
import tempfile
from pathlib import Path
from zipfile import ZipFile
from PySide6.QtGui import QPixmap, QColor

from config import ConfigManager
from export.document_exporter import DocumentExporter
from storage import create_storage_backend
from ui.companion_window import CompanionWindow


def run_smoke_test(app):
    with tempfile.TemporaryDirectory(prefix="cupi-smoke-") as temporary:
        base = Path(temporary)
        (base / "portable.flag").touch()
        config = ConfigManager(create_storage_backend(base))
        window = CompanionWindow(config, discover_models=False)
        image = QPixmap(160, 80)
        image.fill(QColor("red"))
        result = DocumentExporter.export_finalized_doc(
            "# Release check\n\n1. Verify evidence [Image 1]\n\n| Format | Status |\n| --- | --- |\n| Word | Ready |",
            [image], "Release check", str(base / "exports"),
        )
        for key in ("pdf_path", "docx_path", "html_path", "md_path", "zip_path"):
            if not Path(result[key]).is_file() or not Path(result[key]).stat().st_size:
                raise RuntimeError(f"Missing smoke export: {key}")
        if not Path(result["pdf_path"]).read_bytes().startswith(b"%PDF"):
            raise RuntimeError("PDF smoke output is invalid")
        with ZipFile(result["docx_path"]) as document:
            if "word/document.xml" not in document.namelist():
                raise RuntimeError("Word smoke output is invalid")
        if "data:image/png;base64," not in Path(result["html_path"]).read_text():
            raise RuntimeError("HTML evidence was not embedded")
        if window.platform.name == "linux-wayland":
            helper = window.platform._toplevel_capture_helper()
            if not helper:
                raise RuntimeError("Native Hyprland helper missing from Linux bundle")
        window.close()
        app.processEvents()
    print("CᵘPⁱ smoke test passed: UI, PDF, Word, HTML, Markdown, ZIP")

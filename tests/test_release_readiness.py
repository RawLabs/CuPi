import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QProcess
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication

from ai.safe_markdown import sanitize_markdown, SafeMarkdownDocument
from capture.picker_overlay import PickerOverlay
from config import ConfigManager
from export.document_exporter import DocumentExporter
from storage import create_storage_backend
from ui.companion_window import CompanionWindow


def isolated_config(tmp_path):
    (tmp_path / 'portable.flag').touch()
    return ConfigManager(create_storage_backend(tmp_path))


def test_export_rejects_unattached_images_and_host_links(tmp_path):
    private = QPixmap(40, 20)
    private.fill(QColor('blue'))
    private_path = tmp_path / 'private.png'
    private.save(str(private_path))
    evidence = QPixmap(30, 15)
    evidence.fill(QColor('red'))
    text = (f'# Test\n\n![secret]({private_path})\n\n![secret](../../private.png)\n\n'
            '![remote](https://example.test/tracker.png)\n\n![ref][image]\n\n'
            f'[image]: {private_path}\n\n[Run](javascript:alert(1))\n\n[File](file:///private)\n\n'
            '1. Legitimate step [Image 1]')
    result = DocumentExporter.export_finalized_doc(text, [evidence], 'Test', str(tmp_path / 'exports'))
    markdown = Path(result['md_path']).read_text()
    assert str(private_path) not in markdown
    assert '../../private.png' not in markdown
    assert 'tracker.png' not in markdown
    assert 'javascript:' not in markdown
    assert 'file:///private' not in markdown
    html = Path(result['html_path']).read_text()
    assert 'data:image/png;base64,' in html
    assert "img-src data:" in html
    with ZipFile(result['docx_path']) as document:
        images = [name for name in document.namelist() if name.startswith('word/media/')]
        assert len(images) == 1
        decoded = QPixmap()
        assert decoded.loadFromData(document.read(images[0]))
        assert decoded.toImage().pixelColor(0, 0) == QColor('red')


def test_safe_markdown_preserves_examples_and_trusted_export_links():
    text = '```markdown\n![example](/some/file.png)\n```\n\n[Docs](https://example.com)'
    sanitized = sanitize_markdown(text)
    assert '/some/file.png' in sanitized
    assert 'https://example.com' in sanitized
    assert 'file:///tmp/export.html' not in sanitize_markdown('[Export](file:///tmp/export.html)')
    assert 'file:///tmp/export.html' in sanitize_markdown('[Export](file:///tmp/export.html)', trusted_links=True)
    assert SafeMarkdownDocument().loadResource(2, None) is None


@pytest.mark.skipif(os.name != 'posix', reason='POSIX permission semantics')
def test_config_modes_and_failed_write_preserve_previous_config(tmp_path):
    config = isolated_config(tmp_path)
    previous_mask = os.umask(0o022)
    try:
        config.set('openrouter_key', 'test-value')
    finally:
        os.umask(previous_mask)
    assert config.config_file.stat().st_mode & 0o777 == 0o600
    assert config.config_dir.stat().st_mode & 0o777 == 0o700
    original = config.config_file.read_bytes()
    with patch('config.json.dump', side_effect=OSError('write failure')):
        assert config.save() is False
    assert config.config_file.read_bytes() == original
    assert list(config.config_dir.glob('.config-*.tmp')) == []
    assert config.get('captures_dir') == str(config.storage.layout.captures)


def test_export_allocation_failure_does_not_remove_existing_directory(tmp_path):
    existing = tmp_path / 'Test_20261003_120000'
    existing.mkdir()
    important = existing / 'keep.txt'
    important.write_text('keep')
    with patch('export.document_exporter.time.strftime', return_value='20261003_120000'), patch.object(Path, 'mkdir', side_effect=OSError('unavailable')):
        with pytest.raises(OSError):
            DocumentExporter.export_finalized_doc('# Test', [], 'Test', str(tmp_path))
    assert important.read_text() == 'keep'


def test_export_preserves_orphan_zip(tmp_path):
    previous = tmp_path / 'Test_20261003_120000.zip'
    previous.write_bytes(b'keep existing archive')
    with patch('export.document_exporter.time.strftime', return_value='20261003_120000'):
        result = DocumentExporter.export_finalized_doc('# Test', [], 'Test', str(tmp_path))
    assert previous.read_bytes() == b'keep existing archive'
    assert Path(result['doc_dir']).name.endswith('_1')


def test_picker_does_not_use_slurp_on_x11_and_falls_back_if_start_fails():
    picker = PickerOverlay()
    with patch('capture.picker_overlay.QGuiApplication.platformName', return_value='xcb'), patch('capture.picker_overlay.shutil.which', return_value='/usr/bin/slurp'), patch.object(picker, '_show_native_picker') as native, patch.object(picker, '_show_qt_overlay') as fallback:
        picker.show_overlay()
    native.assert_not_called()
    fallback.assert_called_once()
    with patch.object(picker, '_show_qt_overlay') as fallback:
        picker._on_native_picker_error(QProcess.ProcessError.FailedToStart)
    fallback.assert_called_once()


def test_repeat_query_and_failed_request_preserve_snapshot(tmp_path):
    config = isolated_config(tmp_path)
    with patch.object(CompanionWindow, 'fetch_models'):
        window = CompanionWindow(config)
    try:
        window.model_combo.addItem('test-model')
        image = QPixmap(20, 10)
        image.fill(QColor('red'))
        window.attached_pixmaps = [image]
        window.attached_images_b64 = ['test-image']
        worker = Mock()
        worker.isRunning.return_value = False
        with patch('ui.companion_window.InferenceWorker', return_value=worker) as factory:
            window.send_query_with_prompt('Create a guide')
            window.send_query_with_prompt('Second request')
        assert factory.call_count == 1
        assert len(window.conversation.messages) == 1
        window._on_ai_error('connection failed')
        assert window.conversation.messages == []
        assert window.attached_images_b64 == ['test-image']
        assert window.prompt_input.text() == 'Create a guide'
        assert window.send_btn.isEnabled()
    finally:
        window.inference_worker = None
        window.close()


def test_model_refresh_coalesces_and_close_defers_running_request(tmp_path):
    with patch.object(CompanionWindow, 'fetch_models'):
        window = CompanionWindow(isolated_config(tmp_path))
    worker = Mock()
    worker.isRunning.return_value = True
    window.model_fetch_worker = worker
    try:
        with patch('ui.companion_window.ModelFetchWorker') as factory:
            window.fetch_models()
        factory.assert_not_called()
        assert window._model_refresh_pending
        event = Mock()
        with patch('ui.companion_window.QTimer.singleShot'):
            window.closeEvent(event)
        event.ignore.assert_called_once()
        worker.quit.assert_not_called()
        worker.wait.assert_not_called()
    finally:
        window.model_fetch_worker = None
        window.close()


def test_unaccepted_restored_hosted_provider_starts_local(tmp_path):
    config = isolated_config(tmp_path)
    config.data['active_provider'] = 'openrouter'
    config.data['openrouter_privacy_accepted'] = False
    with patch.object(CompanionWindow, 'fetch_models'):
        window = CompanionWindow(config)
    assert config.get('active_provider') == 'lmstudio'
    assert window.provider_combo.currentIndex() == 0
    window.close()


def test_closing_live_inference_keeps_worker_alive_until_finish(tmp_path):
    import threading
    from PySide6.QtTest import QTest
    from ai.provider_client import InferenceWorker

    release = threading.Event()

    class SlowInference(InferenceWorker):
        def run(self):
            release.wait(2)
            self.response_ready.emit('Finished')

    window = CompanionWindow(isolated_config(tmp_path), discover_models=False)
    window.model_combo.addItem('test-model')
    window.show()
    try:
        with patch('ui.companion_window.InferenceWorker', SlowInference):
            window.send_query_with_prompt('Create a guide')
        assert window.inference_worker.parent() is QApplication.instance()
        window.close()
        assert window._closing
        assert window.isVisible()
        release.set()
        QTest.qWait(250)
        assert not window.isVisible()
        assert window.inference_worker is None
    finally:
        release.set()
        QTest.qWait(50)
        window.close()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from xml.etree import ElementTree as ET

from PySide6.QtGui import QColor, QPixmap
from export.document_exporter import DocumentExporter


class TestDocumentExporter(unittest.TestCase):
    def test_rich_markdown_and_literal_html(self):
        html = DocumentExporter._build_html_document(
            'Guide <test>',
            '# Guide\n\n| Item | Value |\n| --- | --- |\n| Mode | Local |\n\n'
            '```python\nprint("<example>")\n```\n\n'
            '1. First\n2. Second\n\n[Docs](https://example.com)\n\n<script>alert(1)</script>',
        )
        self.assertIn('<table', html)
        self.assertIn('<pre', html)
        self.assertIn('<ol', html)
        self.assertIn('href="https://example.com"', html)
        self.assertNotIn('<script>', html)
        self.assertIn('Guide &lt;test&gt;', html)

    def test_evidence_stays_with_its_step(self):
        text = '1. Open settings\n   Choose preferences\n2. Select model\n3. Save'
        rendered = DocumentExporter._insert_evidence(text, 1, './images/step_01.png')
        self.assertLess(rendered.index('step_01.png'), rendered.index('2. Select'))
        self.assertGreater(rendered.index('step_01.png'), rendered.index('Choose preferences'))
        rendered = DocumentExporter._insert_evidence('[Image 10]\n\nOther content', 1, './images/step_01.png')
        self.assertIn('### Step 1 Screenshot', rendered)

    def test_export_bundle_all_formats_and_unique_folders(self):
        pixmap = QPixmap(80, 40)
        pixmap.fill(QColor('red'))
        text = '# Sample Guide\n\n1. Open settings [Image 1]\n2. Save\n\n| Option | Value |\n| --- | --- |\n| Mode | Local |'
        with tempfile.TemporaryDirectory() as directory:
            with patch('export.document_exporter.time.strftime', return_value='20261003_120000'):
                first = DocumentExporter.export_finalized_doc(text, [pixmap], 'Sample Guide', directory)
                second = DocumentExporter.export_finalized_doc(text, [], 'Sample Guide', directory)
            self.assertNotEqual(first['doc_dir'], second['doc_dir'])
            for key in ('pdf_path', 'docx_path', 'html_path', 'md_path', 'zip_path'):
                self.assertGreater(Path(first[key]).stat().st_size, 0)
            pdf_bytes = Path(first['pdf_path']).read_bytes()
            self.assertTrue(pdf_bytes.startswith(b'%PDF'))
            self.assertIn(b'/Subtype /Image', pdf_bytes)
            html = Path(first['html_path']).read_text(encoding='utf-8')
            self.assertIn('data:image/png;base64,', html)
            self.assertNotIn('src="./images/', html)
            self.assertEqual(Path(first['md_path']).read_text(encoding='utf-8').count('# Sample Guide'), 1)
            with ZipFile(first['docx_path']) as word:
                root = ET.fromstring(word.read('word/document.xml'))
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                self.assertEqual(len(root.findall('.//w:tbl', ns)), 1)
                self.assertTrue(any(name.startswith('word/media/') for name in word.namelist()))
                self.assertIn('Local', ''.join(root.itertext()))
            with ZipFile(first['zip_path']) as bundle:
                for extension in ('.pdf', '.docx', '.html', '.md', '.png'):
                    self.assertTrue(any(name.endswith(extension) for name in bundle.namelist()))

    def test_failed_export_removes_partial_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('export.office_exporter.export_docx', side_effect=OSError('write failed')):
                with self.assertRaisesRegex(OSError, 'write failed'):
                    DocumentExporter.export_finalized_doc('# Test', [], 'Test', directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

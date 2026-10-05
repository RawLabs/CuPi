import base64
import html
import shutil
import re
import time
from pathlib import Path
from typing import List, Dict, Optional
from PySide6.QtGui import QPixmap, QTextDocument
from storage import create_storage_backend
from ai.safe_markdown import SafeMarkdownDocument, sanitize_markdown


class DocumentExporter:
    @staticmethod
    def get_export_base_dir() -> Path:
        base_dir = create_storage_backend().layout.exports
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @classmethod
    def sanitize_title_slug(cls, raw_title: str) -> str:
        if not raw_title:
            return "SOP_Guide"

        # Strip HTML/XML tags, markdown symbols, and leading step numbers like "1. ", "Step 1:"
        text = re.sub(r'<[^>]+>', '', raw_title)
        text = re.sub(r'^\s*(\d+[\.\)]|step\s*\d+[:\.]?)\s*', '', text, flags=re.IGNORECASE)
        text = re.sub(r'[\*\#_`]', '', text)

        words = text.split()
        stop_words = {'from', 'the', 'main', 'locate', 'select', 'click', 'then', 'shows', 'doing', 'please', 'write', 'up', 'and', 'for', 'in', 'is', 'of', 'to', 'at'}
        
        filtered = [w for w in words if w.lower() not in stop_words and len(w) > 1]
        if not filtered:
            filtered = words

        slug = "_".join(w.capitalize() for w in filtered[:5])
        slug = re.sub(r'[^\w\-]', '_', slug).strip('_')
        slug = re.sub(r'_+', '_', slug)
        return slug[:40] or "SOP_Guide"

    @classmethod
    def export_finalized_doc(
        cls,
        response_text: str,
        attached_pixmaps: List[QPixmap],
        title: str = "SOP_Guide",
        custom_export_dir: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Export PDF, DOCX, standalone HTML, Markdown, PNG evidence, and a ZIP.
        Place evidence under its matching step without consuming later steps.
        """
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_title = cls.sanitize_title_slug(title)
        folder_name = f"{safe_title}_{ts}"

        if custom_export_dir:
            base_dir = Path(custom_export_dir)
        else:
            base_dir = cls.get_export_base_dir()

        doc_dir = base_dir / folder_name
        created_dir = False
        archive_created = False
        try:
            images_dir = doc_dir / "images"
            base_dir.mkdir(parents=True, exist_ok=True)
            suffix = 1
            while True:
                try:
                    doc_dir.mkdir()
                    if doc_dir.with_suffix(".zip").exists():
                        doc_dir.rmdir()
                        raise FileExistsError("An archive already uses this export name")
                    created_dir = True
                    break
                except FileExistsError:
                    doc_dir = base_dir / f"{folder_name}_{suffix}"
                    suffix += 1
            images_dir = doc_dir / "images"
            images_dir.mkdir()

            saved_image_rel_paths = []
            for idx, pixmap in enumerate(attached_pixmaps, start=1):
                if pixmap and not pixmap.isNull():
                    img_filename = f"step_{idx:02d}.png"
                    img_path = images_dir / img_filename
                    if not pixmap.save(str(img_path), "PNG"):
                        shutil.rmtree(doc_dir)
                        raise OSError(f"Could not save screenshot {idx} to {img_path}")
                    saved_image_rel_paths.append(f"./images/{img_filename}")
                else:
                    saved_image_rel_paths.append("")

            # Process Markdown text & insert images for each step
            md_content = sanitize_markdown(response_text)

            for idx, rel_path in enumerate(saved_image_rel_paths, start=1):
                if rel_path:
                    md_content = cls._insert_evidence(md_content, idx, rel_path)

            # Both formats use the same title and content. HTML embeds local evidence
            # so it can be shared on its own without losing screenshots.
            display_title = title.replace('_', ' ').strip()
            if not re.match(r"^\s*#\s+", md_content):
                md_content = f"# {display_title}\n\n{md_content}"
            html_content = cls._build_html_document(display_title, md_content)
            for rel_path in saved_image_rel_paths:
                if rel_path:
                    encoded = base64.b64encode((doc_dir / rel_path).read_bytes()).decode("ascii")
                    html_content = html_content.replace(
                        f'src="{rel_path}"', f'src="data:image/png;base64,{encoded}"'
                    )

            md_file_path = doc_dir / f"{safe_title}.md"
            html_file_path = doc_dir / f"{safe_title}.html"

            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(md_content)

            with open(html_file_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            from export.office_exporter import export_pdf, export_docx
            pdf_path = doc_dir / f"{safe_title}.pdf"
            docx_path = doc_dir / f"{safe_title}.docx"
            export_pdf(md_content, doc_dir, pdf_path)
            export_docx(md_content, doc_dir, docx_path)

            # Reserve the archive without overwriting an existing artifact.
            archive = doc_dir.with_suffix(".zip")
            with archive.open("xb"):
                archive_created = True
            zip_path = shutil.make_archive(str(doc_dir), "zip", root_dir=base_dir, base_dir=doc_dir.name)

            return {
                "zip_path": zip_path,
                "pdf_path": str(pdf_path),
                "docx_path": str(docx_path),
                "doc_dir": str(doc_dir),
                "md_path": str(md_file_path),
                "html_path": str(html_file_path)
            }

        except Exception:
            if created_dir:
                shutil.rmtree(doc_dir, ignore_errors=True)
            if archive_created:
                doc_dir.with_suffix(".zip").unlink(missing_ok=True)
            raise

    @staticmethod
    def _insert_evidence(markdown: str, index: int, path: str) -> str:
        lines = markdown.splitlines()
        image = f"![Step {index} Screenshot]({path})"
        candidates = []
        in_code = False
        for position, line in enumerate(lines):
            if re.match(r"^\s*(```|~~~)", line):
                in_code = not in_code
            if in_code:
                continue
            if re.search(rf"\bImage\s+{index}\b", line, re.IGNORECASE):
                candidates.append((0, position))
            elif re.match(rf"^\s*(?:#{{1,6}}\s+)?(?:\*\*)?Step\s+{index}\b", line, re.IGNORECASE):
                candidates.append((1, position))
            elif re.match(rf"^\s*{index}[.)]\s+", line):
                candidates.append((2, position))
        if not candidates:
            return markdown.rstrip() + f"\n\n### Step {index} Screenshot\n\n{image}\n"
        _, start = min(candidates)
        end = start + 1
        # Keep a step's continuation with its screenshot, stopping at the next
        # section/list item. Do not consume every following numbered step.
        while end < len(lines):
            if not lines[end].strip() or re.match(r"^\s*(?:#{1,6}\s|\d+[.)]\s|(?:\*\*)?Step\s+\d+\b)", lines[end], re.IGNORECASE):
                break
            end += 1
        lines[end:end] = ["", image, ""]
        return "\n".join(lines)

    @staticmethod
    def _build_html_document(title: str, md_text: str) -> str:
        document = SafeMarkdownDocument()
        document.setMarkdown(
            md_text,
            QTextDocument.MarkdownFeature.MarkdownDialectGitHub
            | QTextDocument.MarkdownFeature.MarkdownNoHTML,
        )
        rendered = document.toHtml()
        content_html = re.search(r"<body[^>]*>(.*?)</body>", rendered, re.DOTALL).group(1)
        clean_title = html.escape(title.replace('_', ' '))

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{clean_title}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --text-color: #f8fafc;
            --h1-color: #38bdf8;
            --h2-color: #7dd3fc;
            --h3-color: #e0f2fe;
            --p-color: #e2e8f0;
            --strong-color: #38bdf8;
            --card-bg: #1e293b;
            --card-border: #0284c7;
            --caption-color: #94a3b8;
        }}

        body.light-mode {{
            --bg-color: #ffffff;
            --text-color: #0f172a;
            --h1-color: #0284c7;
            --h2-color: #0369a1;
            --h3-color: #0f172a;
            --p-color: #334155;
            --strong-color: #0284c7;
            --card-bg: #f8fafc;
            --card-border: #cbd5e1;
            --caption-color: #64748b;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            max-width: 860px;
            margin: 40px auto;
            padding: 24px;
            line-height: 1.6;
            transition: background-color 0.2s, color 0.2s;
        }}

        .toolbar {{
            display: flex;
            justify-content: flex-end;
            gap: 10px;
            margin-bottom: 20px;
        }}

        .btn {{
            background-color: #1e293b;
            color: #38bdf8;
            border: 1px solid #0284c7;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 13px;
            font-weight: bold;
            cursor: pointer;
            transition: all 0.2s;
        }}

        body.light-mode .btn {{
            background-color: #f1f5f9;
            color: #0284c7;
            border-color: #94a3b8;
        }}

        .btn:hover {{
            opacity: 0.9;
            transform: translateY(-1px);
        }}

        h1 {{ color: var(--h1-color); border-bottom: 2px solid var(--card-border); padding-bottom: 8px; }}
        h2 {{ color: var(--h2-color); margin-top: 24px; }}
        h3 {{ color: var(--h3-color); margin-top: 18px; }}
        p {{ color: var(--p-color); font-size: 15px; }}
        ul {{ padding-left: 20px; color: var(--p-color); }}
        li {{ color: var(--p-color); margin-bottom: 6px; }}
        strong {{ color: var(--strong-color); }}

        .img-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 12px;
            margin: 20px 0;
            text-align: center;
            break-inside: avoid;
            page-break-inside: avoid;
        }}

        .img-card img {{
            max-width: 100%;
            border-radius: 6px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        }}

        .caption {{
            color: var(--caption-color);
            font-size: 12px;
            margin-top: 8px;
            font-weight: bold;
        }}

        table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
        td, th {{ border: 1px solid var(--card-border); padding: 8px; }}
        pre {{ white-space: pre-wrap; overflow-wrap: anywhere; padding: 12px; background: var(--card-bg); }}
        code {{ font-family: monospace; }}
        a {{ color: var(--h1-color); overflow-wrap: anywhere; }}
        img {{ max-width: 100%; height: auto; }}
        blockquote {{ border-left: 3px solid var(--card-border); margin-left: 0; padding-left: 16px; }}

        /* Print Optimization (Saves Ink Automatically) */
        @media print {{
            .no-print {{ display: none !important; }}
            body {{
                background-color: #ffffff !important;
                color: #0f172a !important;
                max-width: 100% !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            h1 {{ color: #0284c7 !important; border-bottom: 2px solid #0284c7 !important; }}
            h2, h3 {{ color: #0f172a !important; }}
            p, li {{ color: #1e293b !important; }}
            strong {{ color: #0284c7 !important; }}
            .img-card {{
                background-color: #ffffff !important;
                border: 1px solid #cbd5e1 !important;
                box-shadow: none !important;
            }}
            .img-card img {{
                box-shadow: none !important;
                max-height: 480px;
            }}
        }}
    </style>
</head>
<body>
    <div class="toolbar no-print">
        <button class="btn" onclick="document.body.classList.toggle('light-mode')">☀️ / 🌙 Toggle Theme</button>
        <button class="btn" onclick="window.print()">🖨️ Print / Save PDF</button>
    </div>
    {content_html}
</body>
</html>"""

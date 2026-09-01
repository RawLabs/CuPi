import os
import re
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from PyQt6.QtGui import QPixmap
from storage import create_storage_backend


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
        Exports response_text paired with attached_pixmaps into a finalized document bundle.
        Intelligently places image N under Step N, [Image N], or numbered section N.
        """
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_title = cls.sanitize_title_slug(title)
        folder_name = f"{safe_title}_{ts}"

        if custom_export_dir:
            base_dir = Path(custom_export_dir)
        else:
            base_dir = cls.get_export_base_dir()

        doc_dir = base_dir / folder_name
        images_dir = doc_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        saved_image_rel_paths = []
        for idx, pixmap in enumerate(attached_pixmaps, start=1):
            if pixmap and not pixmap.isNull():
                img_filename = f"step_{idx:02d}.png"
                img_path = images_dir / img_filename
                pixmap.save(str(img_path), "PNG")
                saved_image_rel_paths.append(f"./images/{img_filename}")
            else:
                saved_image_rel_paths.append("")

        # Process Markdown text & insert images for each step
        md_content = response_text

        for idx, rel_path in enumerate(saved_image_rel_paths, start=1):
            if not rel_path:
                continue

            md_img_tag = f"\n\n![Step {idx} Screenshot]({rel_path})\n\n"
            placed = False

            # Pattern 1: Explicit image placeholders like [Image 1], **[Image 1]**, (Image 1), etc.
            pattern_placeholder = re.compile(rf'(\*\*\[?Image\s*{idx}\]?\*\*|\(?\[?Image\s*{idx}\]?\)?)', re.IGNORECASE)
            if pattern_placeholder.search(md_content):
                md_content = pattern_placeholder.sub(rf'\1\n{md_img_tag}', md_content, count=1)
                placed = True

            # Pattern 2: "Step 1" or "Step 1:" or "Step 1."
            if not placed:
                pattern_step = re.compile(rf'(\bStep\s*{idx}\b[:\.]?.*?\n(?:[^\n]+\n)*?)(\n|\Z|(?=\bStep\s*{idx+1}\b|\n\d+[\.\)]))', re.IGNORECASE)
                match = pattern_step.search(md_content)
                if match:
                    start, end = match.span(1)
                    md_content = md_content[:end] + md_img_tag + md_content[end:]
                    placed = True

            # Pattern 3: Numbered list item starting with "1. " or "1) " or "1. **"
            if not placed:
                pattern_num = re.compile(rf'(\n|^)({idx}[\.\)]\s+.*?\n(?:(?!\n?\d+[\.\)]|\n?#).*\n)*)', re.DOTALL)
                match = pattern_num.search(md_content)
                if match:
                    start, end = match.span(2)
                    md_content = md_content[:end] + md_img_tag + md_content[end:]
                    placed = True

            # Pattern 4: Fallback - append to end of document if still not placed
            if not placed:
                md_content += f"\n\n### Step {idx} Screenshot\n{md_img_tag}"

        # Generate HTML Document
        html_content = cls._build_html_document(safe_title, md_content)

        md_file_path = doc_dir / f"{safe_title}.md"
        html_file_path = doc_dir / f"{safe_title}.html"

        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(f"# {title.replace('_', ' ')}\n\n{md_content}")

        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return {
            "doc_dir": str(doc_dir),
            "md_path": str(md_file_path),
            "html_path": str(html_file_path)
        }

    @staticmethod
    def _build_html_document(title: str, md_text: str) -> str:
        lines = md_text.splitlines()
        html_lines = []
        in_list = False

        for line in lines:
            line_str = line.strip()
            if not line_str:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                continue

            # Inline image markdown ![alt](path)
            img_match = re.search(r'!\[(.*?)\]\((.*?)\)', line_str)
            if img_match:
                if in_list:
                    html_lines.append("</ul>")
                    in_list = False
                alt_text, img_src = img_match.groups()
                html_lines.append(f'<div class="img-card"><img src="{img_src}" alt="{alt_text}"><div class="caption">{alt_text}</div></div>')
                continue

            # Headers
            if line_str.startswith("# "):
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append(f'<h1>{line_str[2:]}</h1>')
            elif line_str.startswith("## "):
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append(f'<h2>{line_str[3:]}</h2>')
            elif line_str.startswith("### "):
                if in_list: html_lines.append("</ul>"); in_list = False
                html_lines.append(f'<h3>{line_str[4:]}</h3>')
            elif line_str.startswith("- ") or line_str.startswith("* "):
                if not in_list:
                    html_lines.append("<ul>")
                    in_list = True
                formatted_li = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line_str[2:])
                html_lines.append(f'<li>{formatted_li}</li>')
            elif re.match(r'^\d+[\.\)]\s', line_str):
                if in_list: html_lines.append("</ul>"); in_list = False
                formatted_step = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line_str)
                html_lines.append(f'<h3>{formatted_step}</h3>')
            else:
                if in_list: html_lines.append("</ul>"); in_list = False
                formatted_p = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line_str)
                html_lines.append(f'<p>{formatted_p}</p>')

        if in_list:
            html_lines.append("</ul>")

        content_html = "\n".join(html_lines)
        clean_title = title.replace('_', ' ')

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
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

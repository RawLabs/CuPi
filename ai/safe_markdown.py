"""Keep provider Markdown inert at display and document boundaries."""
from urllib.parse import urlsplit

from PySide6.QtGui import QTextCursor, QTextDocument


class SafeMarkdownDocument(QTextDocument):
    def loadResource(self, resource_type, name):
        # QTextDocument's default loader may read local files. Evidence is
        # registered explicitly by callers instead of granting output that access.
        return None


def sanitize_markdown(text: str, allowed_images=(), trusted_links: bool = False) -> str:
    document = SafeMarkdownDocument()
    document.setMarkdown(
        text,
        QTextDocument.MarkdownFeature.MarkdownDialectGitHub
        | QTextDocument.MarkdownFeature.MarkdownNoHTML,
    )
    edits = []
    block = document.begin()
    while block.isValid():
        iterator = block.begin()
        while not iterator.atEnd():
            fragment = iterator.fragment()
            if fragment.isValid():
                fmt = fragment.charFormat()
                if fmt.isImageFormat() and fmt.toImageFormat().name() not in allowed_images:
                    edits.append((fragment.position(), fragment.length(), None))
                elif fmt.isAnchor():
                    scheme = urlsplit(fmt.anchorHref()).scheme.lower()
                    allowed = scheme in {"http", "https", "mailto"} or (trusted_links and scheme == "file")
                    if not allowed:
                        fmt.setAnchor(False)
                        fmt.setAnchorHref("")
                        edits.append((fragment.position(), fragment.length(), fmt))
            iterator += 1
        block = block.next()
    for position, length, fmt in reversed(edits):
        cursor = QTextCursor(document)
        cursor.setPosition(position)
        cursor.setPosition(position + length, QTextCursor.MoveMode.KeepAnchor)
        if fmt is None:
            cursor.insertText("[Image omitted]")
        else:
            cursor.setCharFormat(fmt)
    return document.toMarkdown()

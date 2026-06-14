from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from .file_scanner import read_markdown_file
from .markdown_renderer import RenderedDocument, render_markdown_text


class RenderSignals(QObject):
    finished = Signal(object, object)
    error = Signal(object, str)


class RenderWorker(QRunnable):
    """Render Markdown off the UI thread, useful for very large docs."""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self.signals = RenderSignals()

    @Slot()
    def run(self) -> None:
        try:
            markdown_text = read_markdown_file(self.path)
            rendered: RenderedDocument = render_markdown_text(markdown_text, self.path)
            self.signals.finished.emit(self.path, rendered)
        except Exception as exc:
            self.signals.error.emit(self.path, str(exc))

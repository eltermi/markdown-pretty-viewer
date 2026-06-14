from __future__ import annotations

from pathlib import Path

from .config import MARKDOWN_EXTENSIONS


def find_markdown_files(folder: Path) -> list[Path]:
    """Find Markdown files directly inside a folder, non-recursively."""
    return sorted(
        [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in MARKDOWN_EXTENSIONS],
        key=lambda path: path.name.lower(),
    )


def read_markdown_file(path: Path) -> str:
    """Read Markdown text with sensible UTF-8 handling."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8-sig")

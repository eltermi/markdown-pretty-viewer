from __future__ import annotations

import os
import stat
import tempfile
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
    return path.read_bytes().decode("utf-8")


def write_markdown_file(path: Path, content: str) -> None:
    """Replace the file atomically so a failed write never truncates the original."""
    target = path.resolve(strict=True)
    mode = stat.S_IMODE(target.stat().st_mode)
    fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

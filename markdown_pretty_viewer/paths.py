from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    """Return project/bundle root in development or PyInstaller runtime."""
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def resource_path(relative_path: str) -> Path:
    return project_root() / relative_path

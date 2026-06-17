from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings


class AppSettings:
    """Small wrapper around QSettings for user preferences.

    QSettings stores preferences in the native location for each OS:
    - macOS: user preferences
    - Windows: registry/AppData-backed settings
    """

    LAST_MARKDOWN_FOLDER = "folders/last_markdown_folder"
    LAST_MARKDOWN_FILE = "files/last_markdown_file"
    LAST_EXPORT_FOLDER = "folders/last_export_folder"

    def __init__(self) -> None:
        self._settings = QSettings()

    def _get_existing_path(self, key: str, *, folder_only: bool = False) -> Optional[Path]:
        value = self._settings.value(key, "", type=str)
        if not value:
            return None

        path = Path(value).expanduser()
        if folder_only:
            return path if path.is_dir() else None
        return path if path.exists() else None

    def last_markdown_folder(self) -> Optional[Path]:
        return self._get_existing_path(self.LAST_MARKDOWN_FOLDER, folder_only=True)

    def set_last_markdown_folder(self, folder: Path) -> None:
        self._settings.setValue(self.LAST_MARKDOWN_FOLDER, str(folder))

    def last_markdown_file(self) -> Optional[Path]:
        return self._get_existing_path(self.LAST_MARKDOWN_FILE)

    def set_last_markdown_file(self, file_path: Path) -> None:
        self._settings.setValue(self.LAST_MARKDOWN_FILE, str(file_path))

    def last_export_folder(self) -> Optional[Path]:
        return self._get_existing_path(self.LAST_EXPORT_FOLDER, folder_only=True)

    def set_last_export_folder(self, folder: Path) -> None:
        self._settings.setValue(self.LAST_EXPORT_FOLDER, str(folder))

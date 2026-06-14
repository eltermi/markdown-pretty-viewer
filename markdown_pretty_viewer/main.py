from __future__ import annotations

import os
import sys
import traceback

from PySide6.QtWidgets import QApplication

from .config import APP_NAME, ORG_NAME
from .ui import MarkdownPrettyViewer


def main() -> int:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-logging --disable-gpu")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    window = MarkdownPrettyViewer()
    window.show()
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise

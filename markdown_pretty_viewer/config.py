from __future__ import annotations

APP_NAME = "Markdown Pretty Viewer"
ORG_NAME = "Local Tools"
BUNDLE_ID = "local.markdown-pretty-viewer"
VERSION = "1.1.0"

MARKDOWN_EXTENSIONS = {".md", ".markdown"}

# Soft warning only. Large files still work, but conversion can take longer.
LARGE_FILE_WARNING_BYTES = 2 * 1024 * 1024

WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 820

BLOCKED_NETWORK_SCHEMES = {"http", "https", "ftp", "ws", "wss"}

from __future__ import annotations

from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor

from .config import BLOCKED_NETWORK_SCHEMES


class LocalOnlyInterceptor(QWebEngineUrlRequestInterceptor):
    """Block network requests so previews remain local-only."""

    def interceptRequest(self, info):  # noqa: N802 - Qt API name
        scheme = info.requestUrl().scheme().lower()
        if scheme in BLOCKED_NETWORK_SCHEMES:
            info.block(True)

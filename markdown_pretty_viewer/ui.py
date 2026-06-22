from __future__ import annotations

import html
import os
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRunnable, QThreadPool, Qt, QTimer, QUrl, Signal, QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtWebEngineCore import QWebEngineProfile, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from .config import APP_NAME, LARGE_FILE_WARNING_BYTES, WINDOW_HEIGHT, WINDOW_WIDTH
from .file_scanner import find_markdown_files
from .markdown_renderer import RenderedDocument
from .settings import AppSettings
from .web_security import LocalOnlyInterceptor
from .workers import RenderWorker


class PdfExportState(QObject):
    finished = Signal(str, bool)


class MarkdownPrettyViewer(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)

        self.current_folder: Optional[Path] = None
        self.current_markdown_file: Optional[Path] = None
        self.current_html = ""
        self._preview_html_path: Optional[Path] = None
        self._last_render_request: Optional[Path] = None
        self._pdf_print_started = False
        self.settings = AppSettings()
        self._pdf_state = PdfExportState()
        self._pdf_state.finished.connect(self._on_pdf_finished)
        self.thread_pool = QThreadPool.globalInstance()

        self._setup_web_profile()
        self._setup_ui()
        self._show_empty_state()
        self._restore_last_session()

    def _setup_web_profile(self) -> None:
        self.interceptor = LocalOnlyInterceptor(self)
        profile = QWebEngineProfile.defaultProfile()
        profile.setUrlRequestInterceptor(self.interceptor)

    def _setup_ui(self) -> None:
        central = QWidget(self)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(8)

        toolbar_row = QHBoxLayout()
        toolbar_row.setSpacing(8)

        self.choose_folder_button = QPushButton("Seleccionar carpeta")
        self.choose_folder_button.clicked.connect(self.choose_folder)
        toolbar_row.addWidget(self.choose_folder_button)

        self.export_pdf_button = QPushButton("Exportar PDF")
        self.export_pdf_button.clicked.connect(self.export_pdf)
        self.export_pdf_button.setEnabled(False)
        toolbar_row.addWidget(self.export_pdf_button)

        self.export_html_button = QPushButton("Exportar HTML")
        self.export_html_button.clicked.connect(self.export_html)
        self.export_html_button.setEnabled(False)
        toolbar_row.addWidget(self.export_html_button)

        self.folder_label = QLabel("Ninguna carpeta seleccionada")
        self.folder_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.folder_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar_row.addWidget(self.folder_label, stretch=1)

        root_layout.addLayout(toolbar_row)

        splitter = QSplitter(Qt.Horizontal)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.list_label = QLabel("Archivos Markdown")
        left_layout.addWidget(self.list_label)

        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self.on_file_selected)
        left_layout.addWidget(self.file_list)

        splitter.addWidget(left_panel)

        self.web_view = QWebEngineView()
        self.web_view.setContextMenuPolicy(Qt.NoContextMenu)
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        splitter.addWidget(self.web_view)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([285, 915])
        root_layout.addWidget(splitter, stretch=1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self._setup_menu()

    def _setup_menu(self) -> None:
        file_menu = self.menuBar().addMenu("Archivo")

        select_action = QAction("Seleccionar carpeta…", self)
        select_action.triggered.connect(self.choose_folder)
        file_menu.addAction(select_action)

        export_pdf_action = QAction("Exportar PDF…", self)
        export_pdf_action.triggered.connect(self.export_pdf)
        file_menu.addAction(export_pdf_action)

        export_html_action = QAction("Exportar HTML…", self)
        export_html_action.triggered.connect(self.export_html)
        file_menu.addAction(export_html_action)

        file_menu.addSeparator()

        quit_action = QAction("Salir", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)


    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self._preview_html_path and self._preview_html_path.exists():
            try:
                self._preview_html_path.unlink()
            except OSError:
                pass
        super().closeEvent(event)

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecciona una carpeta con archivos Markdown",
            str(self.current_folder or self.settings.last_markdown_folder() or Path.home()),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if not folder:
            self.statusBar().showMessage("Selección de carpeta cancelada.", 4000)
            return

        self.current_folder = Path(folder)
        self.settings.set_last_markdown_folder(self.current_folder)
        self.folder_label.setText(str(self.current_folder))
        self.load_markdown_files(self.current_folder)

    def load_markdown_files(self, folder: Path, preferred_file: Optional[Path] = None) -> None:
        self.file_list.clear()
        self.current_markdown_file = None
        self.current_html = ""
        self._set_export_enabled(False)

        try:
            markdown_files = find_markdown_files(folder)
        except Exception as exc:
            self._show_error("No se pudo leer la carpeta", str(exc))
            self._show_empty_state()
            return

        if not markdown_files:
            self._show_message_page(
                "No se encontraron archivos Markdown",
                "La carpeta seleccionada no contiene archivos .md ni .markdown.",
            )
            self.statusBar().showMessage("No se encontraron archivos Markdown en la carpeta seleccionada.", 6000)
            return

        for path in markdown_files:
            item = QListWidgetItem(path.name)
            item.setData(Qt.UserRole, str(path))
            self.file_list.addItem(item)

        self.statusBar().showMessage(f"{len(markdown_files)} archivo(s) Markdown encontrado(s).", 5000)

        preferred_file = preferred_file or self.settings.last_markdown_file()
        selected_row = 0
        if preferred_file:
            try:
                preferred_file = preferred_file.resolve()
                for row, markdown_file in enumerate(markdown_files):
                    if markdown_file.resolve() == preferred_file:
                        selected_row = row
                        break
            except OSError:
                selected_row = 0

        self.file_list.setCurrentRow(selected_row)

        # QListWidget does not always emit itemSelectionChanged when restoring a
        # previous session, especially if the first row remains the current row.
        # Trigger the first render explicitly so startup/refresh always shows the
        # selected Markdown document instead of leaving the empty welcome page.
        if markdown_files:
            QTimer.singleShot(0, lambda path=markdown_files[selected_row]: self.render_markdown_file(path))

    def on_file_selected(self) -> None:
        items = self.file_list.selectedItems()
        if not items:
            return
        self.render_markdown_file(Path(items[0].data(Qt.UserRole)))

    def render_markdown_file(self, path: Path) -> None:
        self.current_markdown_file = None
        self.current_html = ""
        self._set_export_enabled(False)
        self._last_render_request = path

        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0

        if file_size >= LARGE_FILE_WARNING_BYTES:
            self.statusBar().showMessage("Documento grande detectado. Renderizando sin bloquear la interfaz…")
        else:
            self.statusBar().showMessage(f"Renderizando: {path.name}…")

        worker = RenderWorker(path)
        worker.signals.finished.connect(self._on_render_finished)
        worker.signals.error.connect(self._on_render_error)
        self.thread_pool.start(worker)


    def _load_preview_html(self, html_text: str) -> None:
        """Load preview HTML from a temporary local file.

        QWebEngineView.setHtml stores large documents internally as a data URL.
        That can fail silently once the HTML includes a vendored Mermaid bundle.
        Loading a real local file avoids that limit and keeps relative assets
        working through the document's own <base> tag.
        """
        try:
            if self._preview_html_path and self._preview_html_path.exists():
                try:
                    self._preview_html_path.unlink()
                except OSError:
                    pass

            handle = tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".html",
                prefix="mpv-preview-",
                encoding="utf-8",
                delete=False,
            )
            with handle:
                handle.write(html_text)

            self._preview_html_path = Path(handle.name)
            self.web_view.load(QUrl.fromLocalFile(str(self._preview_html_path)))
        except Exception:
            # Last-resort fallback. Small/error pages should still load this way.
            self.web_view.setHtml(html_text, QUrl.fromLocalFile(str(Path.home()) + os.sep))

    def _on_render_finished(self, path: Path, rendered: object) -> None:
        if path != self._last_render_request:
            return
        document = rendered
        if not isinstance(document, RenderedDocument):
            self._show_error("Error de renderizado", "El renderizador devolvió un resultado inesperado.")
            return

        self.current_markdown_file = path
        self.settings.set_last_markdown_file(path)
        self.current_html = document.html
        self._load_preview_html(document.html)
        self._set_export_enabled(True)
        self.statusBar().showMessage(f"Renderizado: {path.name}", 4000)

    def _on_render_error(self, path: Path, message: str) -> None:
        if path != self._last_render_request:
            return
        self._show_error("No se pudo renderizar el archivo", f"{path.name}\n\n{message}")

    def export_pdf(self) -> None:
        if not self.current_markdown_file or not self.current_html:
            self._show_warning("No hay documento seleccionado", "Selecciona primero un archivo Markdown.")
            return

        pdf_path = self._get_export_path(
            title="Guardar PDF",
            default_suffix=".pdf",
            file_filter="PDF (*.pdf)",
        )
        if pdf_path is None:
            self.statusBar().showMessage("Exportación a PDF cancelada.", 4000)
            return

        self.export_pdf_button.setEnabled(False)
        self.statusBar().showMessage("Preparando documento para PDF…")
        self._print_pdf_when_ready(pdf_path)

    def _print_pdf_when_ready(self, pdf_path: Path, attempt: int = 0) -> None:
        """Wait briefly for asynchronous renderers, such as Mermaid, before printing."""
        page = self.web_view.page()
        script = "Boolean(window.__MPV_MERMAID_READY === undefined || window.__MPV_MERMAID_READY)"

        def handle_ready(ready: object) -> None:
            if bool(ready) or attempt >= 50:
                self._prepare_pdf_layout(pdf_path)
                return
            QTimer.singleShot(100, lambda: self._print_pdf_when_ready(pdf_path, attempt + 1))

        try:
            page.runJavaScript(script, handle_ready)
        except Exception:
            self._start_pdf_print(pdf_path)

    def _prepare_pdf_layout(self, pdf_path: Path) -> None:
        """Prepare the loaded page for PDF export without blocking forever.

        Mermaid rendering is asynchronous. The document template exposes an
        optional window.__MPV_PREPARE_PDF function that scales tall Mermaid SVGs
        before printing. Some WebEngine versions can fail to call the JavaScript
        callback, so this method has a hard timeout and prints anyway.
        """
        self._pdf_print_started = False
        page = self.web_view.page()
        script = """
            (function () {
                try {
                    if (typeof window.__MPV_PREPARE_PDF === 'function') {
                        window.__MPV_PREPARE_PDF();
                    }
                    return true;
                } catch (error) {
                    console.error('PDF preparation failed:', error);
                    return true;
                }
            })();
        """

        def start_once() -> None:
            if self._pdf_print_started:
                return
            self._pdf_print_started = True
            self._start_pdf_print(pdf_path)

        try:
            page.runJavaScript(script, lambda _result: QTimer.singleShot(250, start_once))
            QTimer.singleShot(5000, start_once)
        except Exception:
            start_once()


    def _start_pdf_print(self, pdf_path: Path) -> None:
        self.statusBar().showMessage("Generando PDF…")
        try:
            page = self.web_view.page()
            try:
                page.pdfPrintingFinished.disconnect()
            except Exception:
                pass
            page.pdfPrintingFinished.connect(self._pdf_state.finished)
            page.printToPdf(str(pdf_path))
        except Exception as exc:
            self.export_pdf_button.setEnabled(True)
            self._show_error("No se pudo generar el PDF", str(exc))

    def _on_pdf_finished(self, file_path: str, success: bool) -> None:
        self.export_pdf_button.setEnabled(bool(self.current_html))
        if success:
            self.statusBar().showMessage(f"PDF exportado: {file_path}", 8000)
            QMessageBox.information(self, "PDF exportado", f"PDF guardado correctamente:\n\n{file_path}")
        else:
            self._show_error("No se pudo escribir el PDF", f"Destino: {file_path}")

    def export_html(self) -> None:
        if not self.current_markdown_file or not self.current_html:
            self._show_warning("No hay documento seleccionado", "Selecciona primero un archivo Markdown.")
            return

        html_path = self._get_export_path(
            title="Guardar HTML",
            default_suffix=".html",
            file_filter="HTML (*.html)",
        )
        if html_path is None:
            self.statusBar().showMessage("Exportación a HTML cancelada.", 4000)
            return

        try:
            html_path.write_text(self.current_html, encoding="utf-8")
            self.statusBar().showMessage(f"HTML exportado: {html_path}", 8000)
            QMessageBox.information(self, "HTML exportado", f"HTML guardado correctamente:\n\n{html_path}")
        except Exception as exc:
            self._show_error("No se pudo escribir el HTML", str(exc))


    def _restore_last_session(self) -> None:
        """Load the last used Markdown folder on startup when it still exists."""
        last_folder = self.settings.last_markdown_folder()
        if not last_folder:
            return

        self.current_folder = last_folder
        self.folder_label.setText(str(last_folder))
        self.load_markdown_files(last_folder, preferred_file=self.settings.last_markdown_file())

    def _get_export_path(self, title: str, default_suffix: str, file_filter: str) -> Optional[Path]:
        if not self.current_markdown_file:
            return None

        start_folder = self.settings.last_export_folder() or self.current_markdown_file.parent
        suggested_path = start_folder / f"{self.current_markdown_file.stem}{default_suffix}"

        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            title,
            str(suggested_path),
            file_filter,
            options=QFileDialog.DontConfirmOverwrite,
        )
        if not selected_path:
            return None

        export_path = Path(selected_path)
        if export_path.suffix.lower() != default_suffix:
            export_path = export_path.with_suffix(default_suffix)

        export_path = self._resolve_existing_path(export_path, default_suffix.lstrip(".").upper())
        if export_path is None:
            return None

        self.settings.set_last_export_folder(export_path.parent)
        return export_path

    def _resolve_existing_path(self, path: Path, label: str) -> Optional[Path]:
        if not path.exists():
            return path

        response = QMessageBox.question(
            self,
            f"El {label} ya existe",
            f"Ya existe este archivo:\n\n{path}\n\n¿Quieres sobrescribirlo?\n\nSi eliges No, se creará un nombre alternativo.",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.No,
        )

        if response == QMessageBox.Yes:
            return path
        if response == QMessageBox.Cancel:
            return None

        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 2
        while True:
            candidate = parent / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

    def _set_export_enabled(self, enabled: bool) -> None:
        self.export_pdf_button.setEnabled(enabled)
        self.export_html_button.setEnabled(enabled)

    def _show_empty_state(self) -> None:
        self._show_message_page(
            "Markdown Pretty Viewer",
            "Selecciona una carpeta para ver y exportar documentos Markdown como HTML bonito y PDF.",
        )

    def _show_message_page(self, title: str, message: str) -> None:
        safe_title = html.escape(title)
        safe_message = html.escape(message)
        fallback = f"""
        <!doctype html>
        <html lang=\"es\">
        <head>
          <meta charset=\"utf-8\">
          <style>
            body {{ margin: 0; background: #f6f7f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1f2937; }}
            .empty {{ max-width: 720px; margin: 90px auto; background: white; border: 1px solid #e5e7eb; border-radius: 18px; padding: 48px; box-shadow: 0 18px 50px rgba(15,23,42,.08); }}
            h1 {{ margin: 0 0 16px; font-size: 34px; }}
            p {{ font-size: 18px; line-height: 1.6; color: #4b5563; }}
          </style>
        </head>
        <body><main class=\"empty\"><h1>{safe_title}</h1><p>{safe_message}</p></main></body>
        </html>
        """
        self.web_view.setHtml(fallback, QUrl.fromLocalFile(str(Path.home()) + os.sep))

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
        self.statusBar().showMessage(title, 6000)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)
        self.statusBar().showMessage(title, 5000)

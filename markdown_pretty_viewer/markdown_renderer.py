from __future__ import annotations

import html
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import markdown

from .paths import resource_path


@dataclass(frozen=True)
class RenderedDocument:
    title: str
    source_filename: str
    html: str


@lru_cache(maxsize=1)
def load_css() -> str:
    return resource_path("assets/styles.css").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_template() -> str:
    return resource_path("templates/document.html").read_text(encoding="utf-8")


def human_title_from_path(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or path.name


def markdown_to_body(markdown_text: str) -> str:
    return markdown.markdown(
        markdown_text,
        extensions=[
            "markdown.extensions.extra",
            "markdown.extensions.sane_lists",
            "markdown.extensions.toc",
            "pymdownx.tasklist",
            "pymdownx.superfences",
            "pymdownx.highlight",
        ],
        extension_configs={
            "markdown.extensions.toc": {"permalink": False},
            "pymdownx.tasklist": {"custom_checkbox": True},
            "pymdownx.highlight": {"guess_lang": False, "use_pygments": False},
        },
        output_format="html5",
    )


def wrap_document_html(body_html: str, source_path: Path) -> RenderedDocument:
    title = human_title_from_path(source_path)
    template = load_template()
    full_html = (
        template.replace("{{ title }}", html.escape(title))
        .replace("{{ filename }}", html.escape(source_path.name))
        .replace("{{ css }}", load_css())
        .replace("{{ content }}", body_html)
    )
    return RenderedDocument(title=title, source_filename=source_path.name, html=full_html)


def render_markdown_text(markdown_text: str, source_path: Path) -> RenderedDocument:
    return wrap_document_html(markdown_to_body(markdown_text), source_path)

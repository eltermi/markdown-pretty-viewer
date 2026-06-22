from __future__ import annotations

import html
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import markdown

from .paths import resource_path
from .math_renderer import render_latex_math
from .mermaid_renderer import protect_mermaid_blocks, restore_mermaid_blocks


@dataclass(frozen=True)
class RenderedDocument:
    title: str
    source_filename: str
    html: str


@lru_cache(maxsize=1)
def load_css() -> str:
    return resource_path("assets/styles.css").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_mermaid_js() -> str:
    mermaid_path = resource_path("assets/vendor/mermaid/mermaid.min.js")
    if not mermaid_path.exists():
        return ""
    return mermaid_path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_template() -> str:
    return resource_path("templates/document.html").read_text(encoding="utf-8")



def file_url_for_directory(path: Path) -> str:
    """Return a file:// URL ending in / for use as an HTML <base> href."""
    return path.resolve().as_uri().rstrip("/") + "/"

def human_title_from_path(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").strip().title() or path.name


def markdown_to_body(markdown_text: str) -> str:
    markdown_text, mermaid_blocks = protect_mermaid_blocks(markdown_text)
    markdown_text = render_latex_math(markdown_text)
    markdown_text = restore_mermaid_blocks(markdown_text, mermaid_blocks)
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
        .replace("{{ base_href }}", html.escape(file_url_for_directory(source_path.parent), quote=True))
        .replace("{{ css }}", load_css())
        .replace("{{ mermaid_js }}", load_mermaid_js())
        .replace("{{ content }}", body_html)
    )
    return RenderedDocument(title=title, source_filename=source_path.name, html=full_html)


def render_markdown_text(markdown_text: str, source_path: Path) -> RenderedDocument:
    return wrap_document_html(markdown_to_body(markdown_text), source_path)

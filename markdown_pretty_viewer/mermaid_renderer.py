from __future__ import annotations

import html
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MermaidBlock:
    token: str
    html: str


MERMAID_FENCE_RE = re.compile(
    r"(?ms)^(?P<fence>`{3,}|~{3,})[ \t]*mermaid[ \t]*\n(?P<body>.*?)(?:\n(?P=fence)[ \t]*$)",
)


def protect_mermaid_blocks(markdown_text: str) -> tuple[str, list[MermaidBlock]]:
    """Replace Mermaid fenced code blocks with temporary tokens.

    Mermaid is rendered later in the browser by the vendored mermaid.min.js.
    We protect these blocks before math rendering so characters such as `$`, `\\`,
    or brackets inside diagrams are never interpreted as Markdown math.
    """
    blocks: list[MermaidBlock] = []

    def replace(match: re.Match[str]) -> str:
        source = match.group("body").strip("\n")
        token = f"\u0000MPV_MERMAID_{len(blocks)}\u0000"
        escaped = html.escape(source, quote=False)
        block_html = (
            '<div class="mermaid-wrapper">\n'
            f'<pre class="mermaid">{escaped}</pre>\n'
            '</div>'
        )
        blocks.append(MermaidBlock(token=token, html=block_html))
        return f"\n\n{token}\n\n"

    protected = MERMAID_FENCE_RE.sub(replace, markdown_text)
    return protected, blocks


def restore_mermaid_blocks(markdown_text: str, blocks: list[MermaidBlock]) -> str:
    restored = markdown_text
    for block in blocks:
        restored = restored.replace(block.token, block.html)
    return restored

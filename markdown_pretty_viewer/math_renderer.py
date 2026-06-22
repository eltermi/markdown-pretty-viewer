from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class _ProtectedFragment:
    token: str
    value: str


FENCED_CODE_RE = re.compile(r"(^|\n)(`{3,}|~{3,})[^\n]*\n.*?\n\2(?=\n|$)", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]+?`")

BLOCK_MATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<!\\)\$\$(.+?)(?<!\\)\$\$", re.DOTALL),
    re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
)

INLINE_MATH_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\\\((.+?)\\\)", re.DOTALL),
    # Single-dollar inline math. The guards avoid most accidental matches with
    # money amounts or empty delimiters, while preserving common Markdown math.
    re.compile(r"(?<!\\)(?<!\$)\$(?!\$)(\S(?:[^\n$]*?\S)?)\$(?!\$)"),
)


class MathRenderError(RuntimeError):
    pass


def protect_code_fragments(markdown_text: str) -> tuple[str, list[_ProtectedFragment]]:
    """Temporarily replace code spans/blocks so math is not parsed inside them."""
    fragments: list[_ProtectedFragment] = []

    def replace(match: re.Match[str]) -> str:
        token = f"\u0000MPV_CODE_{len(fragments)}\u0000"
        fragments.append(_ProtectedFragment(token=token, value=match.group(0)))
        return token

    protected = FENCED_CODE_RE.sub(replace, markdown_text)
    protected = INLINE_CODE_RE.sub(replace, protected)
    return protected, fragments


def restore_code_fragments(markdown_text: str, fragments: list[_ProtectedFragment]) -> str:
    restored = markdown_text
    for fragment in fragments:
        restored = restored.replace(fragment.token, fragment.value)
    return restored


def _convert_latex_to_mathml(latex_source: str, *, display: str) -> str:
    """Convert LaTeX math to MathML using latex2mathml.

    The import is intentionally local so the rest of the app can still start and
    show a clear fallback if the dependency is missing in a development setup.
    """
    try:
        from latex2mathml import converter
    except Exception as exc:  # pragma: no cover - dependency/environment issue
        raise MathRenderError("latex2mathml is not installed") from exc

    source = latex_source.strip()
    if not source:
        raise MathRenderError("empty math expression")

    try:
        return converter.convert(source, display=display)
    except TypeError:
        # Older latex2mathml versions did not expose the display kwarg.
        mathml = converter.convert(source)
        if display == "block" and " display=" not in mathml[:80]:
            mathml = mathml.replace("<math", '<math display="block"', 1)
        return mathml
    except Exception as exc:
        raise MathRenderError(str(exc)) from exc


def _render_math(latex_source: str, *, block: bool) -> str:
    display = "block" if block else "inline"
    try:
        mathml = _convert_latex_to_mathml(latex_source, display=display)
    except MathRenderError as exc:
        # Keep the original expression visible rather than deleting content.
        # The HTML comment is intentionally invisible in the app/PDF but useful
        # when exporting HTML to diagnose missing bundled dependencies.
        escaped = html.escape(latex_source.strip())
        error = html.escape(str(exc))
        if block:
            return f'<!-- Math rendering fallback: {error} --><pre class="math math-fallback">$$\n{escaped}\n$$</pre>'
        return f'<!-- Math rendering fallback: {error} --><code class="math math-fallback">${escaped}$</code>'

    wrapper = "div" if block else "span"
    class_name = "math math-block" if block else "math math-inline"
    return f'<{wrapper} class="{class_name}">{mathml}</{wrapper}>'


def _replace_math(patterns: tuple[re.Pattern[str], ...], text: str, replacer: Callable[[str], str]) -> str:
    rendered = text
    for pattern in patterns:
        rendered = pattern.sub(lambda match: replacer(match.group(1)), rendered)
    return rendered


def render_latex_math(markdown_text: str) -> str:
    r"""Render LaTeX math delimiters to local MathML before Markdown conversion.

    Supported delimiters:
    - Block: $$...$$ and \[...\]
    - Inline: $...$ and \(...\)

    No JavaScript, CDN, network access, or external renderer is required.
    """
    protected, fragments = protect_code_fragments(markdown_text)
    protected = _replace_math(
        BLOCK_MATH_PATTERNS,
        protected,
        lambda source: _render_math(source, block=True),
    )
    protected = _replace_math(
        INLINE_MATH_PATTERNS,
        protected,
        lambda source: _render_math(source, block=False),
    )
    return restore_code_fragments(protected, fragments)

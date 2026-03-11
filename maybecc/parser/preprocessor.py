"""Two-phase preprocessor for .mcc source files.

Extracts function bodies and @complexity annotation text before Lark lexing,
replacing them with sentinel tokens. This avoids conflicts between // comment
ignoring and // pseudocode lines inside function bodies, and handles nested
parentheses inside @complexity(O(n) where ...) annotations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


_KEYWORD_RE = re.compile(r"\b(fn|struct|enum)\b")
_COMPLEXITY_RE = re.compile(r"@complexity\s*\(")


@dataclass
class PreprocessResult:
    source: str
    bodies: list[str] = field(default_factory=list)
    complexities: list[str] = field(default_factory=list)


def _extract_balanced(text: str, start: int, open_ch: str, close_ch: str) -> int:
    """Return index one past the matching close delimiter.

    ``start`` must point at the opening delimiter.
    """
    depth = 1
    pos = start + 1
    while pos < len(text) and depth > 0:
        if text[pos] == open_ch:
            depth += 1
        elif text[pos] == close_ch:
            depth -= 1
        pos += 1
    if depth != 0:
        raise SyntaxError(
            f"Unmatched '{open_ch}' at position {start}"
        )
    return pos


def preprocess(source: str) -> PreprocessResult:
    """Extract function bodies and complexity text from raw .mcc source.

    Returns a ``PreprocessResult`` with the modified source (sentinels in place
    of extracted regions) and the extracted body/complexity strings.
    """
    result = PreprocessResult(source=source)

    # --- Phase 1: extract @complexity(...) regions ---
    result.source = _extract_complexities(result.source, result.complexities)

    # --- Phase 2: extract function bodies ---
    result.source = _extract_bodies(result.source, result.bodies)

    return result


def _extract_complexities(source: str, out: list[str]) -> str:
    """Replace every ``@complexity(...)`` with ``__CMPLX_N__``."""
    parts: list[str] = []
    last_end = 0

    for match in _COMPLEXITY_RE.finditer(source):
        paren_start = match.end() - 1  # index of '('
        paren_end = _extract_balanced(source, paren_start, "(", ")")
        inner = source[paren_start + 1 : paren_end - 1]

        parts.append(source[last_end : match.start()])
        parts.append(f"__CMPLX_{len(out)}__")
        out.append(inner.strip())
        last_end = paren_end

    parts.append(source[last_end:])
    return "".join(parts)


def _extract_bodies(source: str, out: list[str]) -> str:
    """Replace function body ``{ ... }`` blocks with ``__BODY_N__`` sentinels.

    Only braces that follow a ``fn`` keyword (with possible params, return
    type, and annotations in between) are extracted.  Braces after ``struct``
    or ``enum`` keywords are left untouched.
    """
    parts: list[str] = []
    last_end = 0
    context: str | None = None
    i = 0

    while i < len(source):
        kw_match = _KEYWORD_RE.match(source, i)
        if kw_match:
            context = kw_match.group(1)
            i = kw_match.end()
            continue

        if source[i] == "{":
            if context == "fn":
                brace_end = _extract_balanced(source, i, "{", "}")
                inner = source[i + 1 : brace_end - 1]
                parts.append(source[last_end:i])
                parts.append(f"__BODY_{len(out)}__")
                out.append(inner)
                last_end = brace_end
                i = brace_end
                context = None
                continue
            else:
                context = None

        i += 1

    parts.append(source[last_end:])
    return "".join(parts)

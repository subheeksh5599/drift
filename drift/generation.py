"""Deterministic generation of derived assets.

The generator is a small, swappable seam. It renders text templates over the
resolved upstream inputs — real output that genuinely depends on its inputs, so
changing an input changes the output. An LLM generator (or ffmpeg for binary
assets) plugs in behind the same interface.

Recipes:
  - template:    render a string with {slot} / {param} placeholders.
  - first_line:  first non-empty line of one named input.
  - hashtags:    extract candidate hashtags from one named input.

Platform fit: a node whose operation names a "platform" has its rendered output
truncated to that network's character limit, so a generated post can never
exceed what the network accepts.
"""

from __future__ import annotations

import re

from .platforms import fit as fit_platform
from .types import CompiledNode

_PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_.-]+)\}")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]{3,}")

_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "your", "have",
    "are", "was", "will", "about", "into", "out", "its", "our", "you",
    "has", "been", "not", "all",
}


class GenerationError(ValueError):
    pass


def render_node(node: CompiledNode, inputs: dict[str, str]) -> str:
    recipe = node.operation.get("recipe", "template")
    by_slot: dict[str, str] = {
        slot.slot: inputs.get(slot.from_key, "") for slot in node.inputs
    }

    if recipe == "first_line":
        src = node.operation.get("input")
        if src is None:
            raise GenerationError(f"node {node.stable_key!r} first_line recipe needs an 'input'")
        rendered = _first_line(by_slot.get(src, ""))

    elif recipe == "hashtags":
        src = node.operation.get("input")
        if src is None:
            raise GenerationError(f"node {node.stable_key!r} hashtags recipe needs an 'input'")
        limit = int(node.operation.get("limit", 5))
        rendered = _extract_hashtags(by_slot.get(src, ""), limit)

    elif recipe == "template":
        template = node.operation.get("template", "")
        context = dict(by_slot)
        for key, value in node.operation.items():
            if key not in ("template", "recipe", "platform", "input", "kind", "limit"):
                context[key] = str(value)
        rendered = _substitute(template, context)

    else:
        raise GenerationError(f"node {node.stable_key!r} has unknown recipe {recipe!r}")

    platform = node.operation.get("platform")
    if platform:
        return fit_platform(rendered, platform).text
    return rendered


def _first_line(text: str) -> str:

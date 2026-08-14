"""Provenance receipt.

`report` prints, for every asset in a built pipeline, its fingerprint, its
output hash, and the exact inputs it was derived from — the receipt that lets
someone confirm what a build shipped without trusting the build record.
"""

from __future__ import annotations

from pathlib import Path

from .build import load_sources
from .compiler import compile_graph
from .orbit import ORBIT_TEMPLATE, PARAM_HANDLE, SOURCE_FILES
from .state import load_state


def report(content_dir: Path, handle: str) -> None:
    load_sources(content_dir, SOURCE_FILES)  # fail loudly if a source is missing
    graph = compile_graph(ORBIT_TEMPLATE, parameters={PARAM_HANDLE: handle})
    state = load_state(content_dir / ".drift")

    if not state:
        print("no build yet — run `drift build` first")
        return

    for key in graph.topological_order:
        node = graph.by_key[key]
        entry = state.get(key)
        if entry is None:
            continue
        inputs = [
            f"{slot.from_key}@{_short(state.get(slot.from_key))}" for slot in node.inputs
        ]
        print(f"{key}")
        print(f"  fingerprint  {entry.fingerprint}")
        print(f"  output_hash  {entry.output_hash}")
        print(f"  inputs       {', '.join(inputs) if inputs else '(source)'}")
        print()


def _short(entry) -> str:
    return entry.output_hash[:8] if entry and entry.output_hash else "?"

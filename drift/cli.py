"""Drift CLI.

plan    — predict what a source edit would rebuild, without touching anything.
build   — rebuild only the stale assets, record state and write a manifest.
verify  — re-hash every asset from disk and confirm the manifest.
report  — print the provenance receipt for the current build.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build, load_sources
from .compiler import GraphCompilationError, compile_graph
from .demo_graph import CREATOR_TEMPLATE, DEFAULT_HANDLE, PARAM_HANDLE
from .enums import ImpactDecision
from .generation import GenerationError
from .impact import compute_impact
from .manifest import verify as verify_build
from .report import report
from .state import load_state

_MARKS = {
    ImpactDecision.REUSE: "REUSE ",
    ImpactDecision.REBUILD: "REBUILD",
    ImpactDecision.BLOCKED: "BLOCKED",
}


def _print_plan(plan) -> None:
    print(f"summary:   {plan.summary()}")
    print(f"plan hash: {plan.plan_hash}")
    print()
    for node in plan.nodes:
        print(f"  {_MARKS[node.decision]}  {node.stable_key:<20} {node.reason}")


def cmd_plan(content_dir: Path, handle: str) -> int:
    source_hashes, _ = load_sources(content_dir)
    graph = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: handle})
    base = load_state(content_dir / ".drift")
    plan = compute_impact(graph, base_states=base, source_content_hashes=source_hashes)
    print(f"template: {graph.template_key} v{graph.template_version}")
    _print_plan(plan)
    return 0


def cmd_build(content_dir: Path, handle: str) -> int:
    result = build(content_dir, handle)
    print(f"build {result.build_id}: {result.summary}")
    print(f"manifest:  {result.manifest_path}")
    print()
    for key in result.rebuild:
        print(f"  rebuilt  {key}")
    for key in result.reuse:
        print(f"  reused   {key}")
    return 0


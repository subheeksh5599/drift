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


def cmd_verify(content_dir: Path, build_id: str | None) -> int:
    ok, failures = verify_build(content_dir / ".drift", build_id)
    if ok:
        print("verify: OK — every asset re-hashes to its recorded digest")
        return 0
    print("verify: FAILED")
    for failure in failures:
        print(f"  - {failure}")
    return 1


def cmd_report(content_dir: Path, handle: str) -> int:
    report(content_dir, handle)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="drift", description="Content pipeline build system.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="Predict what a source edit would rebuild.")
    p.add_argument("content_dir", type=Path)
    p.add_argument("--handle", default=DEFAULT_HANDLE)

    b = sub.add_parser("build", help="Rebuild only the stale assets and record state.")
    b.add_argument("content_dir", type=Path)
    b.add_argument("--handle", default=DEFAULT_HANDLE)

    v = sub.add_parser("verify", help="Re-hash every asset and confirm the manifest.")
    v.add_argument("content_dir", type=Path)
    v.add_argument("--build", dest="build_id", default=None)

    r = sub.add_parser("report", help="Print the provenance receipt for the current build.")
    r.add_argument("content_dir", type=Path)
    r.add_argument("--handle", default=DEFAULT_HANDLE)

    args = parser.parse_args(argv)

    try:
        if args.command == "plan":
            return cmd_plan(args.content_dir, args.handle)
        if args.command == "build":
            return cmd_build(args.content_dir, args.handle)
        if args.command == "verify":
            return cmd_verify(args.content_dir, args.build_id)
        if args.command == "report":
            return cmd_report(args.content_dir, args.handle)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except UnicodeDecodeError:
        print("error: source file is not valid UTF-8 text", file=sys.stderr)
        return 1
    except (GenerationError, GraphCompilationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

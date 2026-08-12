"""Build manifest and release verification.

A build writes a manifest: every asset's output hash, bound by a manifest hash.
`verify` re-reads every file from disk and re-hashes it — change one byte and it
fails. This is the "release proof": a third party can confirm what a build
shipped without trusting the build record.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .canonical import canonical_hash
from .demo_graph import SOURCE_FILES
from .types import CompiledGraph

MANIFEST_SCHEMA = "drift-build-v1"


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _manifest_hash(payload: dict) -> str:
    return canonical_hash({k: v for k, v in payload.items() if k != "manifest_hash"})


def write_manifest(
    state_dir: Path,
    build_id: str,
    graph: CompiledGraph,
    plan,
    output_hashes: dict[str, str],
) -> Path:
    builds_dir = state_dir / "builds"
    builds_dir.mkdir(parents=True, exist_ok=True)

    assets = []
    for key in graph.topological_order:
        node = graph.by_key[key]
        path = SOURCE_FILES[key] if node.node_type.is_source else f"out/{key}.txt"
        assets.append(
            {
                "stable_key": key,
                "node_type": str(node.node_type),
                "output_hash": output_hashes[key],
                "path": path,
            }
        )

    payload = {
        "schema": MANIFEST_SCHEMA,
        "build_id": build_id,
        "template": f"{graph.template_key} v{graph.template_version}",
        "graph_hash": graph.canonical_hash,
        "plan_hash": plan.plan_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "assets": assets,
    }
    payload["manifest_hash"] = _manifest_hash(payload)

    path = builds_dir / f"{build_id}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return path


def verify(state_dir: Path, build_id: str | None = None) -> tuple[bool, list[str]]:

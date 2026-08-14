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
from .enums import output_extension
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
    source_files: dict[str, str],
) -> Path:
    builds_dir = state_dir / "builds"
    builds_dir.mkdir(parents=True, exist_ok=True)

    assets = []
    for key in graph.topological_order:
        node = graph.by_key[key]
        path = (
            source_files[key]
            if node.node_type.is_source
            else f"out/{key}{output_extension(node.node_type)}"
        )
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
    """Re-hash every asset and the manifest. Returns (ok, failures)."""
    builds_dir = state_dir / "builds"

    if build_id is not None:
        path = builds_dir / f"{build_id}.json"
    else:
        path = _latest_manifest(builds_dir)
        if path is None:
            return False, ["no builds found"]

    if not path.exists():
        return False, [f"manifest not found: {path}"]

    payload = json.loads(path.read_text())
    failures: list[str] = []

    recomputed = _manifest_hash(payload)
    if recomputed != payload.get("manifest_hash"):
        failures.append("manifest_hash mismatch (the manifest itself was edited)")

    content_dir = state_dir.parent
    for asset in payload["assets"]:
        file = content_dir / asset["path"]
        if not file.exists():
            failures.append(f"{asset['stable_key']}: file missing ({asset['path']})")
            continue
        digest = _hash_bytes(file.read_bytes())
        if digest != asset["output_hash"]:
            failures.append(f"{asset['stable_key']}: hash mismatch ({asset['path']})")

    return (len(failures) == 0, failures)


def _latest_manifest(builds_dir: Path) -> Path | None:
    """Return the manifest of the most recent build, by its recorded created_at.

    Build ids are random hex, so filename order is meaningless. The
    authoritative order is the timestamp each build wrote into its own manifest.
    """
    manifests = list(builds_dir.glob("*.json"))
    if not manifests:
        return None

    def created_at(path: Path) -> datetime:
        try:
            payload = json.loads(path.read_text())
            return datetime.fromisoformat(payload["created_at"])
        except (KeyError, ValueError, json.JSONDecodeError, OSError):
            return datetime.min

    return max(manifests, key=created_at)

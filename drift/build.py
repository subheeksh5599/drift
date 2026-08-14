"""Build orchestration: impact -> generate only what changed -> record state.

Handles both text and media nodes. Text nodes render deterministically in the
domain; media nodes are dispatched to `drift.infra` (Pillow/ffmpeg). Each node's
inputs are resolved as text or a file path depending on the upstream node's
type, the output bytes are written, and real output hashes are recorded so the
next run's reuse proof agrees with what actually happened.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from .compiler import compile_graph
from .enums import ImpactDecision, output_extension
from .fingerprint import compute_fingerprint, compute_source_fingerprint
from .generation import render_node
from .impact import NodeCacheState, compute_impact
from .manifest import write_manifest
from .state import load_state, save_state


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _kind(node) -> str:
    return "media" if node.node_type.is_media else "text"


def load_sources(content_dir: Path, source_files: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Return (source_content_hashes, source_texts) for every declared source file.

    Raises FileNotFoundError if a declared source file is missing — a missing
    source must fail loudly, not silently hash nothing.
    """
    hashes: dict[str, str] = {}
    texts: dict[str, str] = {}
    for stable_key, filename in source_files.items():
        path = content_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"missing source file: {path}")
        data = path.read_bytes()
        hashes[stable_key] = _hash_bytes(data)
        texts[stable_key] = data.decode("utf-8")
    return hashes, texts


@dataclass(frozen=True)
class BuildResult:
    build_id: str
    summary: str
    rebuild: tuple[str, ...]
    reuse: tuple[str, ...]
    plan_hash: str
    manifest_path: Path


def build(content_dir: Path, template, source_files: dict[str, str], parameters: dict[str, str]) -> BuildResult:
    source_hashes, source_texts = load_sources(content_dir, source_files)
    graph = compile_graph(template, parameters=parameters)

    state_dir = content_dir / ".drift"
    base = load_state(state_dir)
    plan = compute_impact(graph, base_states=base, source_content_hashes=source_hashes)

    out_dir = content_dir / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    decision = {n.stable_key: n.decision for n in plan.nodes}

    resolved_text: dict[str, str] = {}
    output_paths: dict[str, Path] = {}
    output_kind: dict[str, str] = {}
    output_hashes: dict[str, str] = {}

    for key in graph.topological_order:
        node = graph.by_key[key]
        out_path = out_dir / f"{key}{output_extension(node.node_type)}"

        if node.node_type.is_source:
            resolved_text[key] = source_texts[key]
            output_hashes[key] = source_hashes[key]
            output_kind[key] = "text"
            continue

        inputs_slot: dict[str, object] = {}
        inputs_from: dict[str, str] = {}
        for slot in node.inputs:
            up = slot.from_key
            if output_kind.get(up) == "media":
                inputs_slot[slot.slot] = output_paths[up]
            else:
                value = resolved_text.get(up, "")
                inputs_slot[slot.slot] = value
                inputs_from[up] = value

        prev = base.get(key)
        disk_hash = _hash_bytes(out_path.read_bytes()) if out_path.exists() else None
        if (
            decision.get(key) is ImpactDecision.REUSE
            and disk_hash is not None
            and prev is not None
            and disk_hash == prev.output_hash
        ):
            output_paths[key] = out_path
            output_hashes[key] = disk_hash
            output_kind[key] = _kind(node)
            if not node.node_type.is_media:
                resolved_text[key] = out_path.read_text()
            continue

        # Rebuild — or regenerate a reuse whose bytes diverged from the recorded
        # hash (a tampered or externally edited file is never trusted as-is).
        if node.node_type.is_media:
            from .infra.render import render_media

            data = render_media(node, inputs_slot)
            out_path.write_bytes(data)
            output_hashes[key] = _hash_bytes(data)
            output_kind[key] = "media"
        else:
            text = render_node(node, inputs_from)
            out_path.write_text(text)
            resolved_text[key] = text
            output_hashes[key] = _hash_bytes(text.encode("utf-8"))
            output_kind[key] = "text"
        output_paths[key] = out_path

    # Record post-build reality: real fingerprints from real output hashes.
    state: dict[str, NodeCacheState] = {}
    for key in graph.topological_order:
        node = graph.by_key[key]
        if node.node_type.is_source:
            fp = compute_source_fingerprint(node, content_hash=source_hashes[key])
        else:
            fp = compute_fingerprint(
                node, input_refs=output_hashes, template_version=graph.template_version
            )
        state[key] = NodeCacheState(
            fingerprint=fp,
            output_hash=output_hashes[key],
            assets_present=True,
        )
    save_state(state_dir, state)

    build_id = uuid.uuid4().hex[:12]
    manifest_path = write_manifest(state_dir, build_id, graph, plan, output_hashes, source_files)

    return BuildResult(
        build_id=build_id,
        summary=plan.summary(),
        rebuild=plan.rebuild_keys,
        reuse=plan.reuse_keys,
        plan_hash=plan.plan_hash,
        manifest_path=manifest_path,
    )

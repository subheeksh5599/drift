import hashlib

from drift.compiler import compile_graph
from drift.demo_graph import (
    CREATOR_TEMPLATE,
    DEFAULT_HANDLE,
    EXPECTED_HANDLE_REBUILD,
    PARAM_HANDLE,
)
from drift.enums import ImpactDecision, ReasonCode
from drift.fingerprint import compute_fingerprint, compute_source_fingerprint
from drift.impact import NodeCacheState, compute_impact


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _build_base(graph, source_hashes):
    """Simulate a completed first build: every node has a fingerprint and a
    present output, computed with real (non-pending) input refs."""
    output_refs: dict[str, str | None] = {}
    state: dict[str, NodeCacheState] = {}
    for key in graph.topological_order:
        node = graph.by_key[key]
        if node.node_type.is_source:
            content_hash = source_hashes[key]
            fp = compute_source_fingerprint(node, content_hash=content_hash)
            output_refs[key] = content_hash
            state[key] = NodeCacheState(fingerprint=fp, output_hash=content_hash, assets_present=True)
        else:
            fp = compute_fingerprint(node, input_refs=output_refs, template_version=graph.template_version)
            out = _sha(fp)
            output_refs[key] = out
            state[key] = NodeCacheState(fingerprint=fp, output_hash=out, assets_present=True)

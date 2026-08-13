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
    return state


BRIEF_A = "Launch a hydration brand. Dark graphite set, crisp white bottle."
BRIEF_B = "Launch a hydration brand. Dark graphite set, crisp white bottle. New packaging."


def test_compile_is_deterministic():
    g1 = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    g2 = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    assert g1.canonical_hash == g2.canonical_hash
    assert len(g1.nodes) == 9
    assert g1.topological_order[0] == "source.brief"


def test_no_change_is_all_reuse():
    graph = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    source_hashes = {"source.brief": _sha(BRIEF_A)}
    base = _build_base(graph, source_hashes)
    plan = compute_impact(graph, base_states=base, source_content_hashes=source_hashes)
    assert plan.summary() == "0 rebuild / 9 reuse / 0 blocked"


def test_edit_source_cascades_to_everything():
    graph = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    base = _build_base(graph, {"source.brief": _sha(BRIEF_A)})
    plan = compute_impact(
        graph, base_states=base, source_content_hashes={"source.brief": _sha(BRIEF_B)}
    )
    assert len(plan.rebuild_keys) == 9  # source + all 8 derived
    source_impact = next(n for n in plan.nodes if n.stable_key == "source.brief")
    assert source_impact.reason_code is ReasonCode.SOURCE_CONTENT_CHANGED
    title = next(n for n in plan.nodes if n.stable_key == "title")
    assert title.reason_code is ReasonCode.UPSTREAM_FINGERPRINT_CHANGED


def test_edit_handle_rebuilds_only_posts():
    base_graph = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    base = _build_base(base_graph, {"source.brief": _sha(BRIEF_A)})
    changed = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: "@newhandle"})
    plan = compute_impact(
        changed, base_states=base, source_content_hashes={"source.brief": _sha(BRIEF_A)}
    )
    assert plan.summary() == "2 rebuild / 7 reuse / 0 blocked"
    assert set(plan.rebuild_keys) == set(EXPECTED_HANDLE_REBUILD)
    for n in plan.nodes:
        if n.stable_key in EXPECTED_HANDLE_REBUILD:
            assert n.reason_code is ReasonCode.NODE_SPEC_CHANGED
        else:
            assert n.decision is ImpactDecision.REUSE


def test_plan_hash_changes_with_decision():
    graph = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    base = _build_base(graph, {"source.brief": _sha(BRIEF_A)})
    p1 = compute_impact(graph, base_states=base, source_content_hashes={"source.brief": _sha(BRIEF_A)})
    p2 = compute_impact(graph, base_states=base, source_content_hashes={"source.brief": _sha(BRIEF_B)})
    assert p1.plan_hash != p2.plan_hash

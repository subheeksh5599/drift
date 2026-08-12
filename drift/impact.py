"""Impact analysis and the reuse proof.

Side-effect free by construction: this module computes what *would* happen. It
touches no disk, makes no generator call, and writes nothing. Identical inputs
produce an identical plan and plan hash, which is what lets a caller reject a
stale plan.

The cascade works through output references rather than explicit graph walking:
a node that will rebuild advertises a `pending:` placeholder instead of its
previously selected asset hash, so every descendant that consumes it
fingerprints differently and is conservatively invalidated.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .canonical import canonical_hash
from .enums import ImpactDecision, ReasonCode
from .fingerprint import compute_fingerprint, compute_source_fingerprint, pending_output_ref
from .types import CompiledGraph


@dataclass(frozen=True)
class NodeCacheState:
    """What a previous build left for one node, used as the reuse candidate."""

    fingerprint: str | None = None
    output_hash: str | None = None
    assets_present: bool = False
    revoked: bool = False


@dataclass(frozen=True)
class NodeImpact:
    stable_key: str
    decision: ImpactDecision
    reason_code: ReasonCode
    reason: str
    old_fingerprint: str | None
    new_fingerprint: str


@dataclass(frozen=True)
class ImpactPlan:
    graph_hash: str
    nodes: tuple[NodeImpact, ...]
    plan_hash: str

    @property
    def rebuild_keys(self) -> tuple[str, ...]:
        return tuple(n.stable_key for n in self.nodes if n.decision is ImpactDecision.REBUILD)

    @property
    def reuse_keys(self) -> tuple[str, ...]:
        return tuple(n.stable_key for n in self.nodes if n.decision is ImpactDecision.REUSE)

    def summary(self) -> str:
        rebuild = sum(1 for n in self.nodes if n.decision is ImpactDecision.REBUILD)
        reuse = sum(1 for n in self.nodes if n.decision is ImpactDecision.REUSE)
        blocked = sum(1 for n in self.nodes if n.decision is ImpactDecision.BLOCKED)
        return f"{rebuild} rebuild / {reuse} reuse / {blocked} blocked"


def evaluate_reuse_proof(
    *,
    proposed_fingerprint: str,
    candidate: NodeCacheState | None,
) -> ReasonCode | None:
    """Return None when reuse is proven, otherwise the reason it was refused.

    Ordering matters for explanation quality: the cheapest and most informative
    check runs first, so a user sees "the recipe changed" rather than an
    incidental downstream complaint.
    """
    if candidate is None or candidate.fingerprint is None:
        return ReasonCode.CACHE_MISS
    if candidate.fingerprint != proposed_fingerprint:
        return ReasonCode.NODE_SPEC_CHANGED
    if candidate.revoked:
        return ReasonCode.MANUAL_INVALIDATION
    if candidate.output_hash is None:
        return ReasonCode.CACHE_ASSET_MISSING
    if not candidate.assets_present:
        return ReasonCode.CACHE_ASSET_MISSING
    return None


def compute_impact(
    graph: CompiledGraph,
    *,
    base_states: Mapping[str, NodeCacheState],
    source_content_hashes: Mapping[str, str],
    blocked_keys: Mapping[str, str] | None = None,
) -> ImpactPlan:
    """Walk the graph in topological order and decide each node.

    `blocked_keys` maps a stable key to the reason it cannot execute — a missing
    credential or unconfigured capability. Those become BLOCKED rather than
    REBUILD, because promising a rebuild the system cannot perform would be a
    lie the user only discovers after committing.
    """
    blocked_keys = blocked_keys or {}
    by_key = graph.by_key
    template_version = graph.template_version

    output_refs: dict[str, str | None] = {}
    impacts: list[NodeImpact] = []

    for stable_key in graph.topological_order:
        node = by_key[stable_key]
        candidate = base_states.get(stable_key)

        if node.node_type.is_source:
            content_hash = source_content_hashes.get(stable_key)
            if content_hash is None:
                raise ValueError(
                    f"source node {stable_key!r} has no content hash; a source must be "
                    "hashed before impact can be computed"
                )
            proposed = compute_source_fingerprint(node, content_hash=content_hash)
        else:
            proposed = compute_fingerprint(node, input_refs=output_refs, template_version=template_version)

        old_fingerprint = candidate.fingerprint if candidate else None
        rejection = evaluate_reuse_proof(proposed_fingerprint=proposed, candidate=candidate)

        if rejection is None:
            output_refs[stable_key] = candidate.output_hash
            impacts.append(
                NodeImpact(
                    stable_key=stable_key,
                    decision=ImpactDecision.REUSE,
                    reason_code=ReasonCode.EXACT_VALIDATED_REUSE,
                    reason="Recipe, inputs and stored bytes are all unchanged.",
                    old_fingerprint=old_fingerprint,
                    new_fingerprint=proposed,
                )
            )
            continue

        if stable_key in blocked_keys:
            output_refs[stable_key] = None
            impacts.append(
                NodeImpact(
                    stable_key=stable_key,
                    decision=ImpactDecision.BLOCKED,
                    reason_code=ReasonCode.CONFIGURATION_BLOCKED,
                    reason=blocked_keys[stable_key],
                    old_fingerprint=old_fingerprint,
                    new_fingerprint=proposed,
                )
            )
            continue

        reason_code, reason = _refine_rebuild_reason(
            stable_key=stable_key,
            rejection_code=rejection,
            node=node,
            graph=graph,
            output_refs=output_refs,
            base_states=base_states,
        )

        output_refs[stable_key] = pending_output_ref(proposed)
        impacts.append(
            NodeImpact(
                stable_key=stable_key,
                decision=ImpactDecision.REBUILD,
                reason_code=reason_code,
                reason=reason,
                old_fingerprint=old_fingerprint,
                new_fingerprint=proposed,
            )
        )

    nodes = tuple(impacts)
    plan = ImpactPlan(graph_hash=graph.canonical_hash, nodes=nodes, plan_hash="")
    return ImpactPlan(graph_hash=graph.canonical_hash, nodes=nodes, plan_hash=_plan_hash(plan))


def _refine_rebuild_reason(
    *,
    stable_key: str,
    rejection_code: ReasonCode,
    node,
    graph: CompiledGraph,
    output_refs: Mapping[str, str | None],
    base_states: Mapping[str, NodeCacheState],
) -> tuple[ReasonCode, str]:
    """Distinguish "this node's own recipe changed" from "something upstream did".

    Both surface as a fingerprint mismatch, but they are different stories to a
    user. If any upstream node is rebuilding in this same plan, the cause is
    upstream; otherwise the node's own spec or source content moved.
    """
    if rejection_code is not ReasonCode.NODE_SPEC_CHANGED:
        return rejection_code, _generic_reason(rejection_code)

    changed_upstream = sorted(
        {
            slot.from_key
            for slot in node.inputs
            if (ref := output_refs.get(slot.from_key)) is not None and ref.startswith("pending:")
        }
    )
    if changed_upstream:
        return (
            ReasonCode.UPSTREAM_FINGERPRINT_CHANGED,
            f"{', '.join(changed_upstream)} will be rebuilt, so this node's input changes.",
        )

    if node.node_type.is_source:
        return ReasonCode.SOURCE_CONTENT_CHANGED, "The source content changed."

    if stable_key not in base_states:
        return ReasonCode.NODE_ADDED, "This node is new in the proposed graph."

    return ReasonCode.NODE_SPEC_CHANGED, "This node's own specification changed."


def _generic_reason(code: ReasonCode) -> str:
    return {
        ReasonCode.CACHE_MISS: "No previous build produced this node.",
        ReasonCode.MANUAL_INVALIDATION: "This output was manually invalidated.",
        ReasonCode.CACHE_ASSET_MISSING: "The previous build node has no stored output.",
        ReasonCode.CACHE_ASSET_UNVERIFIED: "Stored bytes no longer match the recorded hash.",
    }.get(code, code.value)


def _plan_hash(plan: ImpactPlan) -> str:
    return canonical_hash(
        {
            "graph_hash": plan.graph_hash,
            "nodes": [
                {
                    "stable_key": n.stable_key,
                    "decision": str(n.decision),
                    "reason_code": str(n.reason_code),
                    "new_fingerprint": n.new_fingerprint,
                    "old_fingerprint": n.old_fingerprint,
                }
                for n in plan.nodes
            ],
        }
    )

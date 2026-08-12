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

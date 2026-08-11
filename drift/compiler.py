"""Graph compiler.

Compiles a versioned template against a project revision into an immutable
graph snapshot. Rejects cycles, missing dependencies, duplicate stable keys,
duplicate input slots/ordinals, self-edges, and unresolvable parameter bindings.

Determinism is the contract: output must not depend on input ordering, so the
canonical hash is computed over nodes sorted by stable key while each node's
input array keeps its authored order.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping

from .canonical import JsonValue, canonical_hash, canonical_payload
from .types import (
    SCHEMA_VERSION,
    CompiledGraph,
    CompiledNode,
    GraphTemplate,
    TemplateNode,
    node_spec_hash,
)

COMPILER_VERSION = "1"


class GraphCompilationError(ValueError):
    pass


def compile_graph(
    template: GraphTemplate,
    *,
    parameters: Mapping[str, JsonValue] | None = None,
) -> CompiledGraph:
    """Compile `template` against a revision's parameters."""
    parameters = parameters or {}
    _reject_duplicate_keys(template)
    known_keys = {node.stable_key for node in template.nodes}

    compiled: list[CompiledNode] = []
    for node in template.nodes:
        _validate_inputs(node, known_keys)
        operation = _resolve_operation(node, parameters)
        compiled.append(
            CompiledNode(
                stable_key=node.stable_key,
                node_type=node.node_type,
                label=node.label or node.stable_key,
                inputs=node.inputs,
                operation=operation,
                spec_hash=node_spec_hash(node.stable_key, node.node_type, node.inputs, operation),
            )
        )

    order = topological_order(compiled)
    return CompiledGraph(
        template_key=template.key,
        template_version=template.version,
        nodes=tuple(compiled),
        topological_order=order,
        canonical_hash=_graph_hash(template, compiled),
    )


def _reject_duplicate_keys(template: GraphTemplate) -> None:
    seen: set[str] = set()
    for node in template.nodes:
        if node.stable_key in seen:
            raise GraphCompilationError(f"duplicate stable key in template: {node.stable_key!r}")
        seen.add(node.stable_key)


def _validate_inputs(node: TemplateNode, known_keys: set[str]) -> None:
    seen_slots: set[tuple[str, int]] = set()
    for slot in node.inputs:
        if slot.from_key == node.stable_key:
            raise GraphCompilationError(f"self-edge on node {node.stable_key!r}")
        if slot.from_key not in known_keys:
            raise GraphCompilationError(
                f"node {node.stable_key!r} depends on unknown node {slot.from_key!r}"
            )
        key = (slot.slot, slot.ordinal)
        if key in seen_slots:
            raise GraphCompilationError(
                f"node {node.stable_key!r} has duplicate input slot {slot.slot!r} ordinal {slot.ordinal}"
            )
        seen_slots.add(key)


def _resolve_operation(node: TemplateNode, parameters: Mapping[str, JsonValue]) -> dict:
    """Apply allow-listed parameter bindings, then freeze.

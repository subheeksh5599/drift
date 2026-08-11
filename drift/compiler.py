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

    Only keys named in `parameter_bindings` may be written, and only from the
    revision's `parameters` map. That restriction bounds the blast radius of an
    edit: a parameter can only invalidate the nodes that declare the binding.
    """
    operation = dict(node.operation)
    for binding in node.parameter_bindings:
        if binding.parameter not in parameters:
            raise GraphCompilationError(
                f"node {node.stable_key!r} binds parameter {binding.parameter!r}, "
                "which the project revision does not define"
            )
        operation[binding.operation_key] = parameters[binding.parameter]
    canonical_payload(operation)  # fail loudly now, not at fingerprint time
    return operation


def topological_order(nodes: list[CompiledNode]) -> tuple[str, ...]:
    """Kahn's algorithm, proving acyclicity and yielding a deterministic order."""
    indegree = {node.stable_key: 0 for node in nodes}
    dependents: dict[str, list[str]] = {node.stable_key: [] for node in nodes}

    for node in nodes:
        for upstream in sorted({slot.from_key for slot in node.inputs}):
            indegree[node.stable_key] += 1
            dependents[upstream].append(node.stable_key)

    ready = deque(sorted(key for key, degree in indegree.items() if degree == 0))
    order: list[str] = []
    while ready:
        key = ready.popleft()
        order.append(key)
        newly_ready: list[str] = []
        for dependent in dependents[key]:
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                newly_ready.append(dependent)
        for dependent in sorted(newly_ready):
            ready.append(dependent)
        ready = deque(sorted(ready))

    if len(order) != len(nodes):
        unresolved = sorted(set(indegree) - set(order))
        raise GraphCompilationError(f"graph contains a cycle among nodes: {', '.join(unresolved)}")
    return tuple(order)


def _graph_hash(template: GraphTemplate, nodes: list[CompiledNode]) -> str:
    return canonical_hash(
        {
            "schema_version": SCHEMA_VERSION,
            "compiler_version": COMPILER_VERSION,
            "template_key": template.key,
            "template_version": template.version,
            "nodes": [
                {"stable_key": node.stable_key, "spec_hash": node.spec_hash}

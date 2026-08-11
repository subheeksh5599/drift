"""Graph and node data types."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import canonical_hash
from .enums import NodeType

SCHEMA_VERSION = "drift-graph-v1"


@dataclass(frozen=True)
class InputSlot:
    """One declared dependency: a named slot fed by an upstream node's output."""

    slot: str
    from_key: str
    ordinal: int = 0


@dataclass(frozen=True)
class ParameterBinding:
    """Binds a project-revision parameter into one node's operation.

    Only keys named here may reach a node's operation, which is what bounds the
    blast radius of a parameter edit: change it, and only the nodes that declare
    the binding are invalidated.
    """

    operation_key: str
    parameter: str


@dataclass(frozen=True)
class TemplateNode:
    stable_key: str
    node_type: NodeType
    label: str = ""
    inputs: tuple[InputSlot, ...] = ()
    operation: dict = field(default_factory=dict)
    parameter_bindings: tuple[ParameterBinding, ...] = ()


@dataclass(frozen=True)
class CompiledNode:
    stable_key: str
    node_type: NodeType
    label: str
    inputs: tuple[InputSlot, ...]
    operation: dict  # resolved: parameter bindings applied
    spec_hash: str


@dataclass(frozen=True)

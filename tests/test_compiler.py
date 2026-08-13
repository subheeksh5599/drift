import pytest

from drift.compiler import GraphCompilationError, compile_graph
from drift.demo_graph import CREATOR_TEMPLATE, DEFAULT_HANDLE, PARAM_HANDLE
from drift.enums import NodeType
from drift.types import GraphTemplate, InputSlot, TemplateNode


def test_compile_is_deterministic():
    g1 = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    g2 = compile_graph(CREATOR_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    assert g1.canonical_hash == g2.canonical_hash


def test_rejects_duplicate_keys():
    nodes = (TemplateNode("a", NodeType.SOURCE), TemplateNode("a", NodeType.DERIVED))
    with pytest.raises(GraphCompilationError):
        compile_graph(GraphTemplate("t", 1, nodes))


def test_rejects_unknown_dependency():
    nodes = (TemplateNode("b", NodeType.DERIVED, inputs=(InputSlot("x", "missing"),)),)
    with pytest.raises(GraphCompilationError):
        compile_graph(GraphTemplate("t", 1, nodes))


def test_rejects_self_edge():
    nodes = (TemplateNode("a", NodeType.DERIVED, inputs=(InputSlot("x", "a"),)),)
    with pytest.raises(GraphCompilationError):
        compile_graph(GraphTemplate("t", 1, nodes))


def test_rejects_cycle():
    nodes = (
        TemplateNode("a", NodeType.DERIVED, inputs=(InputSlot("x", "b"),)),
        TemplateNode("b", NodeType.DERIVED, inputs=(InputSlot("x", "a"),)),
    )
    with pytest.raises(GraphCompilationError):
        compile_graph(GraphTemplate("t", 1, nodes))


def test_rejects_missing_bound_parameter():
    with pytest.raises(GraphCompilationError):
        compile_graph(CREATOR_TEMPLATE, parameters={})


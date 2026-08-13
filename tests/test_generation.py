import pytest

from drift.enums import NodeType
from drift.generation import GenerationError, render_node
from drift.types import CompiledNode, InputSlot


def _node(key, operation, inputs=()):
    return CompiledNode(
        stable_key=key,
        node_type=NodeType.DERIVED,
        label=key,
        inputs=tuple(inputs),
        operation=operation,
        spec_hash="test",
    )


def test_first_line_returns_first_nonempty_line():
    node = _node("title", {"recipe": "first_line", "input": "brief"},
                 [InputSlot("brief", "source.brief")])
    text = render_node(node, {"source.brief": "Line one.\nLine two."})
    assert text == "Line one."


def test_first_line_on_empty_input_is_empty():
    node = _node("title", {"recipe": "first_line", "input": "brief"},
                 [InputSlot("brief", "source.brief")])
    assert render_node(node, {"source.brief": ""}) == ""


def test_hashtags_extract_real_words_and_skip_stopwords():
    node = _node("tags", {"recipe": "hashtags", "input": "brief", "limit": 6},
                 [InputSlot("brief", "source.brief")])
    text = render_node(node, {"source.brief": "Launch a hydration brand with a teal orbital line."})
    assert text.startswith("#Launch #Hydration #Brand")
    assert "#With" not in text  # stopword


def test_template_resolves_slots_and_bound_params():
    # A bound parameter is resolved into the operation by the compiler; mirror that.
    node = _node("post", {"template": "{caption} {handle}", "handle": "@me"},
                 [InputSlot("caption", "caption.x")])
    text = render_node(node, {"caption.x": "hello"})
    assert text == "hello @me"


def test_platform_fit_truncates_long_output():
    node = _node("post", {"template": "{brief}", "platform": "x"},
                 [InputSlot("brief", "source.brief")])
    text = render_node(node, {"source.brief": "y" * 500})
    assert len(text) == 280


def test_unresolved_placeholder_raises():
    node = _node("post", {"template": "{missing}"},
                 [InputSlot("caption", "caption.x")])
    with pytest.raises(GenerationError):
        render_node(node, {"caption.x": "hello"})

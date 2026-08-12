"""The demo content pipeline graph.

A creator's real pipeline: one source brief, and every downstream asset derived
from it — title, description, tags, thumbnail caption, per-platform captions and
posts. The `handle` parameter is bound only into the two post nodes, so editing
it invalidates exactly two nodes instead of the whole pipeline.
"""

from __future__ import annotations

from .enums import NodeType
from .types import GraphTemplate, InputSlot, ParameterBinding, TemplateNode

TEMPLATE_KEY = "creator-pipeline"
TEMPLATE_VERSION = 1

PARAM_HANDLE = "handle"
DEFAULT_HANDLE = "@creator"

#: The two nodes a handle edit must invalidate. Asserted by test, never used to
#: shortcut the impact algorithm — the algorithm has to derive it.
EXPECTED_HANDLE_REBUILD = ("post.x", "post.linkedin")

#: The source node -> the file that carries it in a content directory.
SOURCE_FILES = {
    "source.brief": "brief.txt",
}


def _derived(key: str, label: str, inputs, operation=None, bindings=()):
    return TemplateNode(
        stable_key=key,
        node_type=NodeType.DERIVED,
        label=label,
        inputs=tuple(inputs),
        operation=operation or {},
        parameter_bindings=tuple(bindings),
    )


CREATOR_TEMPLATE = GraphTemplate(
    key=TEMPLATE_KEY,
    version=TEMPLATE_VERSION,
    nodes=(
        TemplateNode(
            stable_key="source.brief",
            node_type=NodeType.SOURCE,
            label="Brief / script",
            operation={"kind": "text"},
        ),
        _derived(
            "title", "Title",
            [InputSlot("brief", "source.brief")],
            operation={"recipe": "first_line", "input": "brief"},
        ),
        _derived(
            "description", "Description",
            [InputSlot("brief", "source.brief"), InputSlot("title", "title")],
            operation={"template": "{brief}\n\n{title}"},
        ),
        _derived(
            "tags", "Tags",
            [InputSlot("brief", "source.brief")],
            operation={"recipe": "hashtags", "input": "brief", "limit": 6},
        ),
        _derived(
            "thumbnail_caption", "Thumbnail caption",
            [InputSlot("title", "title")],
            operation={"template": "{title}"},
        ),
        _derived(
            "caption.x", "X caption",
            [InputSlot("title", "title"), InputSlot("description", "description")],
            operation={"platform": "x", "template": "{title}\n\n{description}"},
        ),
        _derived(
            "caption.linkedin", "LinkedIn caption",
            [InputSlot("title", "title"), InputSlot("description", "description")],
            operation={"platform": "linkedin", "template": "{title}\n\n{description}"},
        ),
        _derived(
            "post.x", "X post",
            [InputSlot("caption", "caption.x"), InputSlot("tags", "tags")],
            operation={"platform": "x", "template": "{caption}\n\n{tags} {handle}"},
            bindings=(ParameterBinding("handle", PARAM_HANDLE),),
        ),
        _derived(
            "post.linkedin", "LinkedIn post",
            [InputSlot("caption", "caption.linkedin"), InputSlot("tags", "tags")],
            operation={"platform": "linkedin", "template": "{caption}\n\n{tags} {handle}"},
            bindings=(ParameterBinding("handle", PARAM_HANDLE),),
        ),
    ),
)

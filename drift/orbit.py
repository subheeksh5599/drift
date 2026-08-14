"""The ORBIT launch graph — exactly 18 nodes, text + media.

A creator's full pipeline: two sources (brief + product reference), the text
descendants (title, description, tags, captions, posts), and the generated
media (poster, product cutout, keyframes, narration, delivery package).

The `handle` parameter is bound only into the two post nodes, so editing it
invalidates exactly two nodes instead of the whole pipeline — the same
blast-radius discipline as any volatile copy: keep it in a parameter, not the
source.

Media generation is deterministic (Pillow + ffmpeg), so the whole graph is
content-addressed and verifiable without any non-deterministic model call.
"""

from __future__ import annotations

from .enums import NodeType
from .types import GraphTemplate, InputSlot, ParameterBinding, TemplateNode

TEMPLATE_KEY = "orbit-launch"
TEMPLATE_VERSION = 1

PARAM_HANDLE = "handle"
DEFAULT_HANDLE = "@creator"

#: The two nodes a handle edit must invalidate. Asserted by test, never used to
#: shortcut the impact algorithm — the algorithm has to derive it.
EXPECTED_HANDLE_REBUILD = ("post.x", "post.linkedin")

#: The source node -> the file that carries it in a content directory.
SOURCE_FILES = {
    "source.brief": "brief.txt",
    "source.product": "product.txt",
}

DELIVERABLE_KEYS = ("compose.delivery", "image.poster")


def _src(key: str, label: str) -> TemplateNode:
    return TemplateNode(stable_key=key, node_type=NodeType.SOURCE, label=label, operation={"kind": "text"})


def _derived(key: str, label: str, inputs, operation=None, bindings=()):
    return TemplateNode(
        stable_key=key,
        node_type=NodeType.DERIVED,
        label=label,
        inputs=tuple(inputs),
        operation=operation or {},
        parameter_bindings=tuple(bindings),
    )


def _media(key: str, node_type: NodeType, label: str, inputs, operation):
    return TemplateNode(
        stable_key=key,
        node_type=node_type,
        label=label,
        inputs=tuple(inputs),
        operation=operation,
    )


ORBIT_TEMPLATE = GraphTemplate(
    key=TEMPLATE_KEY,
    version=TEMPLATE_VERSION,
    nodes=(
        # ---- sources ----
        _src("source.brief", "Launch brief"),
        _src("source.product", "Product reference"),

        # ---- text descendants ----
        _derived(
            "plan.shots", "Shot plan",
            [InputSlot("brief", "source.brief")],
            operation={"recipe": "shot_plan", "input": "brief", "shots": 3},
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

        # ---- generated media ----
        _media(
            "image.poster", NodeType.IMAGE, "Poster",
            [InputSlot("title", "title"), InputSlot("product", "source.product")],
            operation={"recipe": "poster"},
        ),
        _media(
            "transform.cutout", NodeType.IMAGE, "Product cutout",
            [InputSlot("product", "source.product")],
            operation={"recipe": "cutout"},
        ),
        _media(
            "image.keyframe.01", NodeType.IMAGE, "Keyframe 1",
            [InputSlot("plan", "plan.shots"), InputSlot("cutout", "transform.cutout")],
            operation={"recipe": "keyframe", "index": 1},
        ),
        _media(
            "image.keyframe.02", NodeType.IMAGE, "Keyframe 2",
            [InputSlot("plan", "plan.shots"), InputSlot("cutout", "transform.cutout")],
            operation={"recipe": "keyframe", "index": 2},
        ),
        _media(
            "image.keyframe.03", NodeType.IMAGE, "Keyframe 3",
            [InputSlot("plan", "plan.shots"), InputSlot("cutout", "transform.cutout")],
            operation={"recipe": "keyframe", "index": 3},
        ),
        _media(
            "audio.narration", NodeType.AUDIO, "Narration",
            [InputSlot("description", "description")],
            operation={"recipe": "narration"},
        ),
        _media(
            "compose.delivery", NodeType.VIDEO, "Delivery package",
            [
                InputSlot("poster", "image.poster"),
                InputSlot("k1", "image.keyframe.01"),
                InputSlot("k2", "image.keyframe.02"),
                InputSlot("k3", "image.keyframe.03"),
                InputSlot("narration", "audio.narration"),
            ],
            operation={"recipe": "delivery"},
        ),
    ),
)

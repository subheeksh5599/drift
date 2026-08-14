"""Shared enums for the graph and impact engine."""

from __future__ import annotations

from enum import StrEnum


class NodeType(StrEnum):
    SOURCE = "SOURCE"      # a real uploaded asset (brief, product reference)
    DERIVED = "DERIVED"    # text derived from upstream nodes
    IMAGE = "IMAGE"        # a generated image (poster, cutout, keyframe)
    AUDIO = "AUDIO"        # a generated audio track (narration)
    VIDEO = "VIDEO"        # a generated video (delivery package)

    @property
    def is_source(self) -> bool:
        return self is NodeType.SOURCE

    @property
    def is_media(self) -> bool:
        return self in (NodeType.IMAGE, NodeType.AUDIO, NodeType.VIDEO)


#: The file extension a generated node of each type is written under.
OUTPUT_EXTENSION = {
    NodeType.SOURCE: ".txt",
    NodeType.DERIVED: ".txt",
    NodeType.IMAGE: ".png",
    NodeType.AUDIO: ".wav",
    NodeType.VIDEO: ".mp4",
}


def output_extension(node_type: NodeType) -> str:
    return OUTPUT_EXTENSION[node_type]


class ImpactDecision(StrEnum):
    REUSE = "REUSE"
    REBUILD = "REBUILD"
    BLOCKED = "BLOCKED"


class ReasonCode(StrEnum):
    # reuse accepted
    EXACT_VALIDATED_REUSE = "EXACT_VALIDATED_REUSE"
    # rebuild / refusal reasons
    CACHE_MISS = "CACHE_MISS"
    NODE_SPEC_CHANGED = "NODE_SPEC_CHANGED"
    UPSTREAM_FINGERPRINT_CHANGED = "UPSTREAM_FINGERPRINT_CHANGED"
    SOURCE_CONTENT_CHANGED = "SOURCE_CONTENT_CHANGED"
    NODE_ADDED = "NODE_ADDED"
    MANUAL_INVALIDATION = "MANUAL_INVALIDATION"
    CACHE_ASSET_MISSING = "CACHE_ASSET_MISSING"
    CACHE_ASSET_UNVERIFIED = "CACHE_ASSET_UNVERIFIED"
    # blocked
    CONFIGURATION_BLOCKED = "CONFIGURATION_BLOCKED"

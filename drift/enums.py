"""Shared enums for the graph and impact engine."""

from __future__ import annotations

from enum import StrEnum


class NodeType(StrEnum):
    SOURCE = "SOURCE"      # a real uploaded asset (video, image, post text)
    DERIVED = "DERIVED"    # an asset generated from upstream assets

    @property
    def is_source(self) -> bool:
        return self is NodeType.SOURCE


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

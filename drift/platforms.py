"""Per-platform formatting constraints.

Real, measured character limits a creator must respect per network. A post that
exceeds its platform's limit is truncated to fit — never silently: the FitResult
reports that a cut happened, so the creator can see the difference.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Platform:
    key: str
    name: str
    char_limit: int


PLATFORMS: dict[str, Platform] = {
    "x": Platform("x", "X / Twitter", 280),
    "threads": Platform("threads", "Threads", 500),
    "linkedin": Platform("linkedin", "LinkedIn", 3000),
    "instagram": Platform("instagram", "Instagram", 2200),
}


@dataclass(frozen=True)
class FitResult:
    text: str
    truncated: bool
    original_length: int
    limit: int


def fit(text: str, platform_key: str) -> FitResult:
    platform = PLATFORMS[platform_key]
    if len(text) <= platform.char_limit:
        return FitResult(
            text=text, truncated=False, original_length=len(text), limit=platform.char_limit
        )
    return FitResult(
        text=text[: platform.char_limit],
        truncated=True,
        original_length=len(text),
        limit=platform.char_limit,
    )

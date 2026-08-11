"""Drift — a build system for a creator's content pipeline.

The idea, in one line: a piece of content is a graph of derived assets
(title, description, tags, thumbnail, clips, captions, per-platform posts).
Every asset is content-addressed from its recipe and its exact inputs, so the
system can prove which assets are stale when the source changes — and rebuild
only those, with a verifiable receipt for every decision.
"""

__version__ = "0.1.0"

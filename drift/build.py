"""Build orchestration: impact -> generate only what changed -> record state.

The impact engine predicts what will rebuild; the build carries it out and
records the post-build reality: every node's real fingerprint, computed from
real output hashes, so the next run's reuse proof agrees with what actually
happened (not with the `pending:` placeholders the plan used to predict).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from .compiler import compile_graph
from .demo_graph import CREATOR_TEMPLATE, PARAM_HANDLE, SOURCE_FILES
from .enums import ImpactDecision
from .fingerprint import compute_fingerprint, compute_source_fingerprint
from .generation import render_node
from .impact import NodeCacheState, compute_impact
from .manifest import write_manifest
from .state import load_state, save_state


def _hash_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_sources(content_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """Return (source_content_hashes, source_texts) for every source file.

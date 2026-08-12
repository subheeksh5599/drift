"""Load and save node cache state from `.drift/state.json`.

The state records, per node, the fingerprint and output hash a previous build
left behind — the reuse candidates the impact engine compares against.
"""

from __future__ import annotations

import json
from pathlib import Path

from .impact import NodeCacheState

STATE_FILENAME = "state.json"


def load_state(state_dir: Path) -> dict[str, NodeCacheState]:
    path = state_dir / STATE_FILENAME
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {
        key: NodeCacheState(
            fingerprint=value.get("fingerprint"),
            output_hash=value.get("output_hash"),
            assets_present=bool(value.get("assets_present", False)),
            revoked=bool(value.get("revoked", False)),
        )
        for key, value in raw.items()
    }


def save_state(state_dir: Path, states: dict[str, NodeCacheState]) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        key: {
            "fingerprint": s.fingerprint,
            "output_hash": s.output_hash,
            "assets_present": s.assets_present,
            "revoked": s.revoked,
        }
        for key, s in sorted(states.items())
    }
    (state_dir / STATE_FILENAME).write_text(json.dumps(payload, indent=2, sort_keys=True))

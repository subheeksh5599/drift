"""Project storage: the content directory and its build artifacts."""

from __future__ import annotations

import json
from pathlib import Path


class ProjectStore:
    def __init__(self, root: Path):
        self.root = root
        self.content = root / "content"
        self.content.mkdir(parents=True, exist_ok=True)

    def write_sources(self, brief: str, product: str) -> None:
        (self.content / "brief.txt").write_text(brief)
        (self.content / "product.txt").write_text(product)

    def latest_manifest(self) -> dict | None:
        builds = self.content / ".drift" / "builds"
        if not builds.exists():
            return None
        manifests = list(builds.glob("*.json"))
        if not manifests:
            return None
        latest = max(manifests, key=lambda p: p.stat().st_mtime)
        return json.loads(latest.read_text())

    def assets(self) -> list[dict]:
        manifest = self.latest_manifest()
        return manifest["assets"] if manifest else []

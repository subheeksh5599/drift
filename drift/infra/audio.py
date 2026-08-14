"""Deterministic audio generation (narration).

Prefers a real text-to-speech path when one is present in this ffmpeg build
(the `flite` filter), otherwise a deterministic synthesized track whose pitch
is seeded by the description. Either way the output is a pure function of the
input text — content-addressed, no model call.
"""

from __future__ import annotations

import hashlib
import subprocess


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


def _has_flite() -> bool:
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=15,
        )
        return "flite" in out.stdout
    except Exception:
        return False


def _flite(text: str) -> bytes:
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"flite=text={text!r}:voice=slt",
         "-f", "wav", "-"],
        capture_output=True, check=True,
    )
    return proc.stdout


def _tone(text: str) -> bytes:
    seed = _seed(text)
    base = 200 + seed % 400
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", f"sine=frequency={base}:duration=3",
         "-af", "afade=t=in:st=0:d=0.2,afade=t=out:st=2.7:d=0.3",
         "-f", "wav", "-"],
        capture_output=True, check=True,
    )
    return proc.stdout


def render_narration(description: str) -> bytes:
    if _has_flite():
        return _flite(description)
    return _tone(description)

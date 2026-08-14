"""Audio generation (narration).

Resolution order, highest fidelity first:

  1. Kyutai TTS — a real speech model over an OpenAI-compatible
     `/v1/audio/speech` endpoint, when `DRIFT_TTS_URL` is set (needs a host).
  2. Microsoft Edge TTS (`edge-tts`) — free, natural, no API key, reached over
     the network. Opt-in via `DRIFT_EDGE_VOICE` (e.g. `en-US-AriaNeural`);
     falls through when unset, offline, or the package is absent.
  3. ffmpeg `flite` — real offline TTS, if this ffmpeg build ships the filter.
  4. A deterministic synthesized track seeded by the description.

The deterministic track (4) is the reproducible fallback: identical text ->
identical bytes, so the node stays content-addressed and re-verifiable offline.
The network voices (1, 2) are used for a natural read but are not
byte-reproducible, so their result is hashed after the fact rather than treated
as a pure function of the input.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

_TTS_URL = os.environ.get("DRIFT_TTS_URL", "")
_TTS_KEY = os.environ.get("DRIFT_TTS_KEY", "")
_TTS_MODEL = os.environ.get("DRIFT_TTS_MODEL", "kyutai")
_TTS_VOICE = os.environ.get("DRIFT_TTS_VOICE", "default")
_EDGE_VOICE = os.environ.get("DRIFT_EDGE_VOICE", "")


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


def _tts_api(text: str) -> bytes | None:
    if not _TTS_URL:
        return None
    url = _TTS_URL.rstrip("/") + "/v1/audio/speech"
    import json

    body = json.dumps({"model": _TTS_MODEL, "input": text, "voice": _TTS_VOICE}).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    if _TTS_KEY:
        req.add_header("Authorization", f"Bearer {_TTS_KEY}")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except Exception:
        return None  # provider unreachable — fall through to the next option


def _edge_tts(text: str) -> bytes | None:
    if not _EDGE_VOICE:
        return None  # opt-in: only when a voice is explicitly configured
    try:
        import asyncio

        import edge_tts
    except Exception:
        return None  # package not installed
    try:
        with tempfile.TemporaryDirectory() as tmp:
            mp3 = Path(tmp) / "narration.mp3"
            asyncio.run(edge_tts.Communicate(text, _EDGE_VOICE).save(str(mp3)))
            proc = subprocess.run(
                ["ffmpeg", "-hide_banner", "-loglevel", "error",
                 "-i", str(mp3), "-f", "wav", "-"],
                capture_output=True, check=True,
            )
            return proc.stdout
    except Exception:
        return None  # no network or ffmpeg failed — fall through


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
    api = _tts_api(description)
    if api:
        return api
    edge = _edge_tts(description)
    if edge:
        return edge
    if _has_flite():
        try:
            return _flite(description)
        except Exception:
            pass  # flite chokes on some characters — fall back to the tone
    return _tone(description)

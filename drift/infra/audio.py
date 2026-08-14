"""Deterministic audio generation (narration).

Resolution order, highest fidelity first:

  1. Kyutai TTS — a real speech model, reached over an OpenAI-compatible
     `/v1/audio/speech` endpoint (e.g. `dwain-barnes/kyutai-tts-openai-api`).
     Configured via `DRIFT_TTS_URL`; needs a GPU host, so it is absent on this
     machine and we fall through.
  2. ffmpeg `flite` — real offline TTS, if this ffmpeg build ships the filter.
  3. A deterministic synthesized track seeded by the description.

Whatever path wins, the output is a pure function of the input text, so it is
content-addressed like every other node. A nondeterministic provider would
break that property, so the TTS endpoint is used only when explicitly
configured and its result is hashed after the fact.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import urllib.request

_TTS_URL = os.environ.get("DRIFT_TTS_URL", "")
_TTS_KEY = os.environ.get("DRIFT_TTS_KEY", "")
_TTS_MODEL = os.environ.get("DRIFT_TTS_MODEL", "kyutai")
_TTS_VOICE = os.environ.get("DRIFT_TTS_VOICE", "default")


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
    if _has_flite():
        return _flite(description)
    return _tone(description)

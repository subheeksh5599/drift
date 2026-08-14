"""Deterministic video composition with ffmpeg.

The delivery package is a real MP4: the poster as the cover frame, the
keyframes as a timed sequence, and the narration track muxed as audio. Every
frame is normalized to a common 1280x720 canvas first, so mixed-size inputs
(poster vs keyframes) still concatenate. ffmpeg is deterministic given
identical inputs, so the video is content-addressed like every other node.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

WIDTH, HEIGHT = 1280, 720


def render_delivery(*, poster: Path, keyframes: list[Path], narration: Path) -> bytes:
    frames = [poster, *keyframes]
    n = len(frames)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "delivery.mp4"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for img in frames:
            cmd += ["-loop", "1", "-t", "1.5", "-i", str(img)]
        cmd += ["-i", str(narration)]

        scale = (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2,setsar=1"
        )
        parts = [f"[{i}:v]{scale}[v{i}]" for i in range(n)]
        concat_src = "".join(f"[v{i}]" for i in range(n))
        cmd += [
            "-filter_complex",
            ";".join(parts) + f";{concat_src}concat=n={n}:v=1:a=0[vid]",
            "-map", "[vid]",
            "-map", f"{n}:a",
            "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-movflags", "+faststart",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out.read_bytes()

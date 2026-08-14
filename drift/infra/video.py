"""Deterministic video composition with ffmpeg.

The delivery package is a real MP4: the poster as the cover frame, the
keyframes as a timed sequence, and the narration track muxed as audio. Each
still is given a slow centred "Ken Burns" zoom and the segments are stitched
with crossfades, so the result feels like a produced reel rather than a
slideshow of hard cuts.

The timeline is driven by the narration length: the segment length is solved
so the whole sequence (with its (n-1) crossfade overlaps) lands exactly on the
narration duration. ffmpeg is deterministic given identical inputs, so the
video is content-addressed like every other node.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

WIDTH, HEIGHT = 1280, 720
FPS = 30
FADE = 0.8  # crossfade seconds between segments
ZOOM = 0.12  # total zoom (12%) applied across a segment


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    try:
        return float(out.stdout.strip())
    except ValueError:
        return 6.0


def _ken_burns(frames: int) -> str:
    # 2x upscale first so the zoompan sub-pixel sampling stays smooth, then a
    # slow centred zoom-in across the whole segment, normalized to the canvas.
    w, h = WIDTH * 2, HEIGHT * 2
    return (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
        f"zoompan=z='1+{ZOOM}*on/{frames}':d={frames}:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={WIDTH}x{HEIGHT}:fps={FPS},setsar=1,format=yuv420p"
    )


def render_delivery(*, poster: Path, keyframes: list[Path], narration: Path) -> bytes:
    frames = [poster, *keyframes]
    n = len(frames)
    total = _duration(narration)

    # Solve segment length so the crossfade-overlapped sequence equals `total`.
    seg = (total + (n - 1) * FADE) / n
    per_seg_frames = max(int(round(FPS * seg)), 1)
    seg = per_seg_frames / FPS  # actual segment length after rounding

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "delivery.mp4"
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for img in frames:
            cmd += ["-i", str(img)]  # single still; zoompan expands it to a segment
        cmd += ["-i", str(narration)]

        parts = [f"[{i}:v]{_ken_burns(per_seg_frames)}[v{i}]" for i in range(n)]

        prev = "[v0]"
        xfades = []
        for i in range(1, n):
            offset = i * (seg - FADE)
            label = f"[x{i}]"
            xfades.append(
                f"{prev}[v{i}]xfade=transition=fade:duration={FADE}:offset={offset:.3f}{label}"
            )
            prev = label

        fade_chain = f"{prev}fade=t=in:st=0:d=0.4"
        if total > 1.2:
            fade_chain += f",fade=t=out:st={total - 0.7:.3f}:d=0.7"
        xfades.append(fade_chain + "[vid]")

        cmd += ["-filter_complex", ";".join(parts + xfades)]
        cmd += ["-map", "[vid]", "-map", f"{n}:a"]
        cmd += ["-t", f"{total:.3f}"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
                "-c:a", "aac", "-movflags", "+faststart", str(out)]
        subprocess.run(cmd, check=True, capture_output=True)
        return out.read_bytes()

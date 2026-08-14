"""Deterministic image generation with Pillow.

Every image is a pure function of its inputs — a poster, product cutout, or
keyframe always renders identical PNG bytes from the same text, so it is
content-addressed and verifiable without any model call.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_PATHS = (
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
)


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


def _font(size: int):
    for p in _FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _theme(seed: int):
    """Deterministic palette: dark graphite background, teal + restrained orange."""
    bg = (18 + seed % 28, 18 + (seed >> 3) % 28, 20 + (seed >> 6) % 28)
    teal = (0, 180 + seed % 60, 170 + (seed >> 2) % 60)
    orange = (245, 130 + seed % 60, 40)
    return bg, teal, orange


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [text]


def render_poster(title: str, product: str) -> bytes:
    seed = _seed(product)
    bg, teal, orange = _theme(seed)
    img = Image.new("RGB", (1080, 1350), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 1080, 18], fill=teal)
    d.rectangle([0, 1332, 1080, 1350], fill=orange)
    d.ellipse([240, 420, 840, 1020], outline=teal, width=6)
    font = _font(72)
    y = 600
    for line in _wrap(title, 18):
        w = d.textlength(line, font=font)
        d.text(((1080 - w) / 2, y), line, font=font, fill=(235, 235, 229))
        y += 84
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_cutout(product: str) -> bytes:
    seed = _seed(product)
    _, teal, orange = _theme(seed)
    img = Image.new("RGBA", (600, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([180, 140, 420, 760], radius=60, fill=(20, 22, 24, 255))
    d.rounded_rectangle([210, 80, 390, 160], radius=18, fill=(40, 44, 48, 255))
    d.rectangle([180, 380, 420, 480], fill=teal + (255,))
    d.rectangle([180, 380, 420, 398], fill=orange + (255,))
    d.ellipse([260, 520, 340, 600], outline=(235, 235, 229, 255), width=4)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_keyframe(plan: str, cutout_path: Path, index: int) -> bytes:
    cutout = Image.open(cutout_path).convert("RGBA")
    cutout = cutout.resize((300, 450))
    bg, teal, orange = _theme(_seed(plan + str(index)))
    img = Image.new("RGB", (1920, 1080), bg)
    img.paste(cutout, (1450, 400), cutout)
    d = ImageDraw.Draw(img)
    d.text((80, 80), f"SHOT {index:02d}", font=_font(54), fill=teal)
    shots = plan.splitlines()
    line = shots[index - 1] if 0 <= index - 1 < len(shots) else plan
    d.text((80, 420), _wrap(line, 40)[0], font=_font(64), fill=(235, 235, 229))
    d.ellipse([80, 700, 560, 900], outline=orange, width=6)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

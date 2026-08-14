"""Deterministic image generation via HTML + headless Chrome.

Each image is a self-contained HTML/CSS/SVG document rendered to a PNG by
headless Chrome — the same technique used to produce hero art and "photos"
without a generative model. The markup is a pure function of the node's
inputs, and Chrome renders identical markup to identical bytes, so the result
is content-addressed and verifiable like every other node.

No model, no GPU, no API key: just markup and a deterministic renderer.
"""

from __future__ import annotations

import base64
import hashlib
import html
import shutil
import subprocess
import tempfile
from pathlib import Path

_CHROME_CANDIDATES = (
    "google-chrome-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
)


def _seed(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:4], "big")


def _theme(seed: int) -> tuple[str, str, str]:
    """Deterministic palette: dark graphite bg, teal orbital, restrained orange."""
    bg = f"#{16 + seed % 24:02x}{16 + (seed >> 3) % 24:02x}{18 + (seed >> 6) % 24:02x}"
    teal = f"#{0:02x}{180 + seed % 60:02x}{170 + (seed >> 2) % 60:02x}"
    orange = f"#{245:02x}{130 + seed % 60:02x}{40:02x}"
    return bg, teal, orange


def _chrome() -> str:
    for name in _CHROME_CANDIDATES:
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("no headless Chrome/Chromium binary found")


def _screenshot(html_doc: str, width: int, height: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        src = tmpdir / "scene.html"
        out = tmpdir / "shot.png"
        src.write_text(html_doc)
        subprocess.run(
            [
                _chrome(),
                "--headless", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                f"--window-size={width},{height}",
                "--virtual-time-budget=900",
                f"--screenshot={out}",
                f"file://{src}",
            ],
            check=True, capture_output=True,
        )
        return out.read_bytes()


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
    bg, teal, orange = _theme(_seed(product))
    lines = _wrap(title, 18)
    title_html = "<br>".join(html.escape(l) for l in lines)
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      * {{ margin:0; box-sizing:border-box; }}
      body {{ width:1080px; height:1350px; background:{bg}; position:relative; overflow:hidden;
             font-family:'DejaVu Sans',sans-serif; }}
      .bar-top {{ position:absolute; top:0; left:0; right:0; height:18px; background:{teal}; }}
      .bar-bot {{ position:absolute; bottom:0; left:0; right:0; height:18px; background:{orange}; }}
      .orbit {{ position:absolute; top:380px; left:200px; width:680px; height:680px;
               border:6px solid {teal}; border-radius:50%; }}
      .orbit2 {{ position:absolute; top:430px; left:250px; width:580px; height:580px;
                border:2px solid {teal}59; border-radius:50%; }}
      .title {{ position:absolute; top:540px; left:90px; right:90px; color:#ebebe5;
               font-size:74px; font-weight:bold; line-height:1.1; text-align:center; }}
    </style></head><body>
      <div class="bar-top"></div><div class="bar-bot"></div>
      <div class="orbit"></div><div class="orbit2"></div>
      <div class="title">{title_html}</div>
    </body></html>"""
    return _screenshot(doc, 1080, 1350)


def render_cutout(product: str) -> bytes:
    _, teal, orange = _theme(_seed(product))
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      * {{ margin:0; box-sizing:border-box; }}
      body {{ width:600px; height:900px; background:#161a1e; position:relative; }}
      .bottle {{ position:absolute; top:140px; left:180px; width:240px; height:620px;
                background:#161a1e; border-radius:60px; }}
      .cap {{ position:absolute; top:80px; left:210px; width:180px; height:80px;
             background:#2c3034; border-radius:18px; }}
      .label {{ position:absolute; top:380px; left:180px; width:240px; height:100px;
               background:{teal}; }}
      .label-top {{ position:absolute; top:380px; left:180px; width:240px; height:18px;
                   background:{orange}; }}
      .ring {{ position:absolute; top:520px; left:260px; width:80px; height:80px;
              border:4px solid #ebebe5; border-radius:50%; }}
    </style></head><body>
      <div class="cap"></div><div class="bottle"></div>
      <div class="label"></div><div class="label-top"></div><div class="ring"></div>
    </body></html>"""
    return _screenshot(doc, 600, 900)


def render_keyframe(plan: str, cutout_path: Path, index: int) -> bytes:
    bg, teal, orange = _theme(_seed(plan + str(index)))
    cutout_b64 = base64.b64encode(cutout_path.read_bytes()).decode()
    shots = plan.splitlines()
    line = shots[index - 1] if 0 <= index - 1 < len(shots) else plan
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>
      * {{ margin:0; box-sizing:border-box; }}
      body {{ width:1920px; height:1080px; background:{bg}; position:relative; overflow:hidden;
             font-family:'DejaVu Sans',sans-serif; }}
      .cutout {{ position:absolute; top:350px; right:120px; width:300px; height:450px; }}
      .shot {{ position:absolute; top:80px; left:80px; color:{teal}; font-size:54px; font-weight:bold;
              letter-spacing:0.2em; }}
      .line {{ position:absolute; top:420px; left:80px; max-width:900px; color:#ebebe5;
              font-size:64px; font-weight:bold; line-height:1.1; }}
      .arc {{ position:absolute; bottom:120px; left:80px; width:480px; height:200px;
             border:6px solid {orange}; border-radius:50% 50% 0 0; border-bottom:0; }}
    </style></head><body>
      <img class="cutout" src="data:image/png;base64,{cutout_b64}" />
      <div class="shot">SHOT {index:02d}</div>
      <div class="line">{html.escape(line)}</div>
      <div class="arc"></div>
    </body></html>"""
    return _screenshot(doc, 1920, 1080)

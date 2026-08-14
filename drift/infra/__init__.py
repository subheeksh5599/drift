"""Media generation — the binary-asset layer.

Deterministic generators. No model, no randomness: images are authored as
HTML/CSS/SVG and rendered by headless Chrome; audio and video are ffmpeg. The
same inputs always render the same bytes, so a generated asset is
content-addressed like any other node in the graph.
"""

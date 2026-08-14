"""Media generation — the binary-asset layer.

Deterministic Pillow + ffmpeg generators. No model, no randomness: the same
inputs always render the same bytes, so a generated image/audio/video is
content-addressed like any other node in the graph.
"""

"""The 18-node ORBIT launch graph — text + media, deterministic end to end."""

import subprocess
import sys

from drift.build import build
from drift.orbit import (
    EXPECTED_HANDLE_REBUILD,
    ORBIT_TEMPLATE,
    PARAM_HANDLE,
    SOURCE_FILES,
)


def _build(content_dir, handle="@creator"):
    return build(content_dir, ORBIT_TEMPLATE, SOURCE_FILES, {PARAM_HANDLE: handle})


def _content(content_dir):
    (content_dir / "brief.txt").write_text(
        "Ship a hydration brand launch. Dark graphite set, crisp white bottle, "
        "teal orbital line, restrained orange accent. Four shots, cinematic."
    )
    (content_dir / "product.txt").write_text(
        "Dark graphite set, crisp white bottle, teal orbital line, orange accent."
    )
    return content_dir


def test_graph_has_exactly_18_nodes():
    assert len(ORBIT_TEMPLATE.nodes) == 18


def test_handle_edit_rebuilds_exactly_two_nodes(tmp_path):
    d = _content(tmp_path)
    _build(d)
    r = _build(d, "@newhandle")
    assert set(r.rebuild) == set(EXPECTED_HANDLE_REBUILD)
    assert r.summary == "2 rebuild / 16 reuse / 0 blocked"


def test_source_edit_cascades_to_everything(tmp_path):
    d = _content(tmp_path)
    _build(d)
    (d / "brief.txt").write_text("An entirely different brief for a different product.")
    r = _build(d)
    # The brief reaches every descendant; only the product-only cutout (whose
    # input, source.product, did not change) is correctly reused.
    assert "16 rebuild" in r.summary
    assert "transform.cutout" in r.reuse
    assert "compose.delivery" in r.rebuild


def test_media_bytes_are_deterministic(tmp_path):
    d = _content(tmp_path)
    _build(d)
    poster = (d / "out" / "image.poster.png").read_bytes()
    _build(d)
    _build(d, "@newhandle")  # handle edit must not touch the poster
    assert (d / "out" / "image.poster.png").read_bytes() == poster


def test_delivery_is_a_real_video(tmp_path):
    d = _content(tmp_path)
    _build(d)
    mp4 = d / "out" / "compose.delivery.mp4"
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=format_name,duration",
         "-of", "csv=p=0", str(mp4)],
        capture_output=True, text=True,
    )
    assert probe.returncode == 0
    assert "mp4" in probe.stdout.lower() or "mov" in probe.stdout.lower()


def test_full_verify_passes(tmp_path):
    d = _content(tmp_path)
    _build(d)
    from drift.manifest import verify

    ok, failures = verify(d / ".drift")
    assert ok, failures

"""The 18-node ORBIT launch graph — text + media, deterministic end to end."""

import subprocess

import pytest

from drift.build import build
from drift.manifest import verify
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


@pytest.fixture(scope="session")
def built(tmp_path_factory):
    """Build the full media graph once; the tests then assert on it and do
    targeted rebuilds. Media generation (headless Chrome + ffmpeg) is slow, so
    rebuilding per-test would be minutes."""
    d = tmp_path_factory.mktemp("orbit")
    _content(d)
    _build(d)
    return d


def test_graph_has_exactly_18_nodes():
    assert len(ORBIT_TEMPLATE.nodes) == 18


def test_fresh_build_has_real_media_and_verifies(built):
    for f in [
        "image.poster.png", "transform.cutout.png",
        "image.keyframe.01.png", "image.keyframe.02.png", "image.keyframe.03.png",
        "audio.narration.wav", "compose.delivery.mp4",
    ]:
        assert (built / "out" / f).stat().st_size > 0, f
    ok, failures = verify(built / ".drift")
    assert ok, failures


def test_delivery_is_a_real_video(built):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=format_name,duration",
         "-of", "csv=p=0", str(built / "out" / "compose.delivery.mp4")],
        capture_output=True, text=True,
    )
    assert probe.returncode == 0
    assert "mp4" in probe.stdout.lower() or "mov" in probe.stdout.lower()


def test_handle_edit_rebuilds_exactly_two_nodes(built):
    poster_before = (built / "out" / "image.poster.png").read_bytes()
    r = _build(built, "@newhandle")
    assert set(r.rebuild) == set(EXPECTED_HANDLE_REBUILD)
    assert r.summary == "2 rebuild / 16 reuse / 0 blocked"
    # The handle can't reach the poster, so its bytes are unchanged.
    assert (built / "out" / "image.poster.png").read_bytes() == poster_before


def test_source_edit_cascades_to_everything(built):
    (built / "brief.txt").write_text("An entirely different brief for a different product.")
    r = _build(built)
    # The brief reaches every descendant; only the product-only cutout (whose
    # input, source.product, did not change) is correctly reused.
    assert "16 rebuild" in r.summary
    assert "transform.cutout" in r.reuse
    assert "compose.delivery" in r.rebuild

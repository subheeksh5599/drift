import json

import pytest

from drift.build import build
from drift.demo_graph import CREATOR_TEMPLATE, PARAM_HANDLE, SOURCE_FILES
from drift.manifest import verify


def _build(content_dir, handle="@creator"):
    return build(content_dir, CREATOR_TEMPLATE, SOURCE_FILES, {PARAM_HANDLE: handle})


def _write_brief(content_dir, brief="Launch a hydration brand.\nSecond line of the brief."):
    (content_dir / "brief.txt").write_text(brief)
    return content_dir


def test_build_writes_all_outputs_and_verifies(tmp_path):
    d = _write_brief(tmp_path)
    r = _build(d)
    assert r.summary == "9 rebuild / 0 reuse / 0 blocked"
    for key in [
        "title", "description", "tags", "thumbnail_caption",
        "caption.x", "caption.linkedin", "post.x", "post.linkedin",
    ]:
        assert (d / "out" / f"{key}.txt").exists()
    assert (d / "out" / "title.txt").read_text() == "Launch a hydration brand."
    ok, failures = verify(d / ".drift")
    assert ok, failures


def test_second_build_reuses_everything_when_unchanged(tmp_path):
    d = _write_brief(tmp_path)
    _build(d)
    r = _build(d)
    assert r.summary == "0 rebuild / 9 reuse / 0 blocked"


def test_handle_edit_rebuilds_only_posts(tmp_path):
    d = _write_brief(tmp_path)
    _build(d)
    r = _build(d, "@newhandle")
    assert r.summary == "2 rebuild / 7 reuse / 0 blocked"
    assert set(r.rebuild) == {"post.x", "post.linkedin"}


def test_source_edit_cascades_to_everything(tmp_path):
    d = _write_brief(tmp_path)
    _build(d)
    (d / "brief.txt").write_text("Completely new brief, nothing shared.")
    r = _build(d)
    assert "9 rebuild" in r.summary


def test_verify_catches_tampering(tmp_path):
    d = _write_brief(tmp_path)
    _build(d)
    (d / "out" / "title.txt").write_text("tampered output")
    ok, failures = verify(d / ".drift")
    assert not ok
    assert any("title" in f for f in failures)


def test_verify_catches_missing_file(tmp_path):
    d = _write_brief(tmp_path)
    _build(d)
    (d / "out" / "tags.txt").unlink()
    ok, failures = verify(d / ".drift")
    assert not ok
    assert any("tags" in f for f in failures)


def test_build_with_missing_source_fails_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        _build(tmp_path)  # no brief.txt


def test_verify_catches_manifest_tampering(tmp_path):
    d = _write_brief(tmp_path)
    r = _build(d)
    payload = json.loads(r.manifest_path.read_text())
    payload["assets"][0]["output_hash"] = "0" * 64
    r.manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    ok, failures = verify(d / ".drift")
    assert not ok
    assert any("manifest_hash" in f for f in failures)


def test_verify_picks_latest_build_not_lexicographic(tmp_path):
    d = _write_brief(tmp_path)
    _build(d)
    _build(d, "@newhandle")
    ok, failures = verify(d / ".drift")
    assert ok, failures


def test_build_regenerates_tampered_output(tmp_path):
    d = _write_brief(tmp_path)
    _build(d)
    (d / "out" / "title.txt").write_text("tampered")
    _build(d)
    assert (d / "out" / "title.txt").read_text() == "Launch a hydration brand."

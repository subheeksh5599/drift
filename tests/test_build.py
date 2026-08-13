import shutil

from drift.build import build
from drift.manifest import verify


def _write_brief(content_dir, brief="Launch a hydration brand.\nSecond line of the brief."):
    (content_dir / "brief.txt").write_text(brief)
    return content_dir


def test_build_writes_all_outputs_and_verifies(tmp_path):
    d = _write_brief(tmp_path)
    r = build(d, "@creator")
    assert r.summary == "9 rebuild / 0 reuse / 0 blocked"
    for key in [
        "title", "description", "tags", "thumbnail_caption",
        "caption.x", "caption.linkedin", "post.x", "post.linkedin",
    ]:
        assert (d / "out" / f"{key}.txt").exists()
    # title is genuinely derived — first line of the brief, not a copy of it.
    assert (d / "out" / "title.txt").read_text() == "Launch a hydration brand."
    ok, failures = verify(d / ".drift")
    assert ok, failures
    assert failures == []


def test_second_build_reuses_everything_when_unchanged(tmp_path):
    d = _write_brief(tmp_path)
    build(d, "@creator")
    r = build(d, "@creator")
    assert r.summary == "0 rebuild / 9 reuse / 0 blocked"


def test_handle_edit_rebuilds_only_posts(tmp_path):
    d = _write_brief(tmp_path)
    build(d, "@creator")
    r = build(d, "@newhandle")
    assert r.summary == "2 rebuild / 7 reuse / 0 blocked"
    assert set(r.rebuild) == {"post.x", "post.linkedin"}


def test_source_edit_cascades_to_everything(tmp_path):
    d = _write_brief(tmp_path)
    build(d, "@creator")
    (d / "brief.txt").write_text("Completely new brief, nothing shared.")
    r = build(d, "@creator")
    assert "9 rebuild" in r.summary


def test_verify_catches_tampering(tmp_path):
    d = _write_brief(tmp_path)
    build(d, "@creator")
    (d / "out" / "title.txt").write_text("tampered output")
    ok, failures = verify(d / ".drift")
    assert not ok
    assert any("title" in f for f in failures)


def test_verify_catches_missing_file(tmp_path):

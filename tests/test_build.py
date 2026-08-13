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

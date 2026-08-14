import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "drift.cli", *args], capture_output=True, text=True
    )


def _content(tmp_path):
    (tmp_path / "brief.txt").write_text("A hydration launch brief.\nSecond line.")
    (tmp_path / "product.txt").write_text("Dark graphite, crisp white bottle.")
    return tmp_path


def test_plan_build_verify_end_to_end(tmp_path):
    d = _content(tmp_path)
    assert _run("plan", str(d)).returncode == 0
    first = _run("build", str(d))
    assert first.returncode == 0
    assert "18 rebuild" in first.stdout
    second = _run("build", str(d))
    assert "0 rebuild / 18 reuse" in second.stdout
    assert _run("verify", str(d)).returncode == 0


def test_handle_edit_via_cli(tmp_path):
    d = _content(tmp_path)
    _run("build", str(d))
    r = _run("build", str(d), "--handle", "@newhandle")
    assert r.returncode == 0
    assert "2 rebuild / 16 reuse" in r.stdout


def test_media_outputs_generated(tmp_path):
    d = _content(tmp_path)
    _run("build", str(d))
    for f in ["image.poster.png", "transform.cutout.png", "audio.narration.wav", "compose.delivery.mp4"]:
        assert (d / "out" / f).exists(), f
    assert (d / "out" / "compose.delivery.mp4").stat().st_size > 0


def test_report_prints_provenance(tmp_path):
    d = _content(tmp_path)
    _run("build", str(d))
    r = _run("report", str(d))
    assert r.returncode == 0
    assert "source.brief" in r.stdout
    assert "compose.delivery" in r.stdout


def test_missing_source_reports_error(tmp_path):
    r = _run("build", str(tmp_path))  # no sources
    assert r.returncode == 1
    assert "error:" in r.stderr

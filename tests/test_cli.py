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


def test_cli_end_to_end(tmp_path):
    d = _content(tmp_path)
    assert _run("plan", str(d)).returncode == 0
    first = _run("build", str(d))
    assert first.returncode == 0
    assert "18 rebuild" in first.stdout
    second = _run("build", str(d))
    assert "0 rebuild / 18 reuse" in second.stdout
    handle = _run("build", str(d), "--handle", "@newhandle")
    assert "2 rebuild / 16 reuse" in handle.stdout
    assert _run("verify", str(d)).returncode == 0
    report = _run("report", str(d))
    assert "compose.delivery" in report.stdout


def test_missing_source_reports_error(tmp_path):
    r = _run("build", str(tmp_path))  # no sources
    assert r.returncode == 1
    assert "error:" in r.stderr

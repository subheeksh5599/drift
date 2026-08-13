import subprocess
import sys
from pathlib import Path


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "drift.cli", *args], capture_output=True, text=True
    )


def _brief(tmp_path):
    (tmp_path / "brief.txt").write_text("A hydration launch brief.\nSecond line.")
    return tmp_path


def test_plan_build_verify_end_to_end(tmp_path):
    d = _brief(tmp_path)
    assert _run("plan", str(d)).returncode == 0
    first = _run("build", str(d))
    assert first.returncode == 0
    assert "9 rebuild" in first.stdout
    second = _run("build", str(d))
    assert "0 rebuild / 9 reuse" in second.stdout
    assert _run("verify", str(d)).returncode == 0


def test_handle_edit_via_cli(tmp_path):
    d = _brief(tmp_path)
    _run("build", str(d))

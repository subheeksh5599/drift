import time

from drift.api.queue import FAILED, PENDING, RUNNING, SUCCEEDED, Queue


def _q(tmp_path):
    return Queue(tmp_path / "queue.db")


def test_submit_is_idempotent_by_key(tmp_path):
    q = _q(tmp_path)
    a, created_a = q.submit({"handle": "@a"}, submission_key="commit-1")
    b, created_b = q.submit({"handle": "@b"}, submission_key="commit-1")
    assert a == b
    assert created_a is True
    assert created_b is False


def test_claim_is_exclusive(tmp_path):
    q = _q(tmp_path)
    q.submit({"handle": "@a"})
    first = q.claim("worker-1")
    second = q.claim("worker-2")
    assert first is not None
    assert second is None  # the only pending job is already leased


def test_heartbeat_extends_lease_then_complete(tmp_path):
    q = _q(tmp_path)
    q.submit({"handle": "@a"})
    job = q.claim("worker-1")
    assert q.heartbeat(job["id"]) is True
    q.complete(job["id"], {"summary": "18 rebuild / 0 reuse / 0 blocked"})
    assert q.get(job["id"])["status"] == SUCCEEDED


def test_fail_retries_then_gives_up(tmp_path):
    q = _q(tmp_path)
    q.submit({"handle": "@a"})
    job = q.claim("worker-1")
    job_id = job["id"]
    q.fail(job_id, "boom")  # attempt 1 -> retry
    assert q.get(job_id)["status"] == PENDING
    q.claim("worker-1")
    q.fail(job_id, "boom")  # attempt 2 -> retry
    assert q.get(job_id)["status"] == PENDING
    q.claim("worker-1")
    q.fail(job_id, "boom")  # attempt 3 -> failed (max_attempts=3)
    assert q.get(job_id)["status"] == FAILED


def test_stalled_lease_is_reclaimed(tmp_path):
    q = _q(tmp_path)
    q.submit({"handle": "@a"})
    job = q.claim("worker-1")
    # Force the lease to expire.
    q.conn.execute("UPDATE jobs SET lease_expires=0 WHERE id=?", (job["id"],))
    q.conn.commit()
    reclaimed = q.claim("worker-2")
    assert reclaimed is not None
    assert reclaimed["id"] == job["id"]
    assert reclaimed["status"] == RUNNING


def test_stats_counts(tmp_path):
    q = _q(tmp_path)
    q.submit({"handle": "@a"})
    q.submit({"handle": "@b"})
    s = q.stats()
    assert s["total"] == 2
    assert s["pending"] == 2

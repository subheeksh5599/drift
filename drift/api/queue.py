"""SQLite-backed durable job queue.

Lease + heartbeat + idempotency on a zero-external-service SQLite file:

  - claim is an atomic UPDATE ... WHERE lease_expires < now, so two workers can
    never claim the same job (compare-and-swap on the lease column).
  - a worker heartbeats to extend its lease while the job runs.
  - a unique submission_key makes submit idempotent — resubmitting the same
    key returns the existing job instead of enqueuing a duplicate.
  - a stalled lease is reclaimed by the next claim (lease_expires < now), and a
    failed job is retried up to max_attempts before it is marked failed.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    submission_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    payload TEXT NOT NULL,
    result TEXT,
    error TEXT,
    worker_id TEXT,
    lease_expires REAL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    completed_at REAL
);
"""

PENDING = "pending"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"

LEASE_SECONDS = 60.0


class Queue:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def submit(self, payload: dict, submission_key: str | None = None) -> tuple[str, bool]:
        """Return (job_id, created). created=False means an existing job was returned."""
        key = submission_key or uuid.uuid4().hex
        now = time.time()
        try:
            job_id = uuid.uuid4().hex
            self.conn.execute(
                "INSERT INTO jobs (id, submission_key, payload, created_at, updated_at) "
                "VALUES (?,?,?,?,?)",
                (job_id, key, json.dumps(payload), now, now),
            )
            self.conn.commit()
            return job_id, True
        except sqlite3.IntegrityError:
            row = self.conn.execute(
                "SELECT id FROM jobs WHERE submission_key=?", (key,)
            ).fetchone()
            return row["id"], False

    def claim(self, worker_id: str) -> dict | None:
        """Atomically claim the oldest claimable job.

        Claimable = pending (no lease) or running with an expired lease (a
        worker that died mid-job). `BEGIN IMMEDIATE` takes the write lock up
        front, so two workers can never claim the same job.
        """
        now = time.time()
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            row = self.conn.execute(
                "SELECT id FROM jobs WHERE status=? "
                "OR (status=? AND lease_expires IS NOT NULL AND lease_expires < ?) "
                "ORDER BY created_at LIMIT 1",
                (PENDING, RUNNING, now),
            ).fetchone()
            if row is None:
                self.conn.execute("COMMIT")
                return None
            job_id = row["id"]
            self.conn.execute(
                "UPDATE jobs SET status=?, worker_id=?, lease_expires=?, attempts=attempts+1, "
                "updated_at=? WHERE id=?",
                (RUNNING, worker_id, now + LEASE_SECONDS, now, job_id),
            )
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        return self.get(job_id)

    def heartbeat(self, job_id: str) -> bool:
        now = time.time()
        cur = self.conn.execute(
            "UPDATE jobs SET lease_expires=?, updated_at=? WHERE id=? AND status=?",
            (now + LEASE_SECONDS, now, job_id, RUNNING),
        )
        self.conn.commit()
        return cur.rowcount == 1

    def complete(self, job_id: str, result: dict) -> None:
        now = time.time()
        self.conn.execute(
            "UPDATE jobs SET status=?, lease_expires=NULL, result=?, error=NULL, "
            "completed_at=?, updated_at=? WHERE id=?",
            (SUCCEEDED, json.dumps(result), now, now, job_id),
        )
        self.conn.commit()

    def fail(self, job_id: str, error: str, retryable: bool = True) -> None:
        now = time.time()
        row = self.get(job_id)
        if row is None:
            return
        retry = retryable and row["attempts"] < row["max_attempts"]
        self.conn.execute(
            "UPDATE jobs SET status=?, error=?, lease_expires=NULL, "
            "completed_at=?, updated_at=? WHERE id=?",
            (PENDING if retry else FAILED, error, now if not retry else None, now, job_id),
        )
        self.conn.commit()

    def get(self, job_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list(self, limit: int = 50) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def stats(self) -> dict:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(status='pending') AS pending, "
            "SUM(status='running') AS running, "
            "SUM(status='succeeded') AS succeeded, "
            "SUM(status='failed') AS failed FROM jobs"
        ).fetchone()
        return {k: (row[k] or 0) for k in ("total", "pending", "running", "succeeded", "failed")}

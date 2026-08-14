"""Worker runtime: lease -> generate -> heartbeat -> complete.

A separate process from the API. It claims jobs from the durable queue, runs
the drift engine over the project's sources, heartbeats its lease while the
(possibly slow, ffmpeg) build runs, and records the result.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from ..build import build
from ..orbit import ORBIT_TEMPLATE, SOURCE_FILES
from .queue import Queue
from .storage import ProjectStore

HEARTBEAT_INTERVAL = 15.0


def run_once(queue: Queue, store: ProjectStore, worker_id: str) -> str | None:
    job = queue.claim(worker_id)
    if job is None:
        return None
    job_id = job["id"]
    payload = json.loads(job["payload"])
    handle = payload.get("handle", "@creator")

    stop = threading.Event()

    def _heartbeat() -> None:
        while not stop.is_set():
            if not queue.heartbeat(job_id):
                return
            stop.wait(HEARTBEAT_INTERVAL)

    thread = threading.Thread(target=_heartbeat, daemon=True)
    thread.start()
    try:
        result = build(store.content, ORBIT_TEMPLATE, SOURCE_FILES, {"handle": handle})
        queue.complete(
            job_id,
            {
                "summary": result.summary,
                "build_id": result.build_id,
                "rebuild": list(result.rebuild),
                "reuse": list(result.reuse),
                "plan_hash": result.plan_hash,
            },
        )
    except Exception as exc:  # a failed job is retried, then failed permanently
        queue.fail(job_id, str(exc))
    finally:
        stop.set()
    return job_id


def serve(queue: Queue, store: ProjectStore, worker_id: str = "worker-1", poll: float = 1.0) -> None:
    while True:
        run_once(queue, store, worker_id)
        time.sleep(poll)


if __name__ == "__main__":
    import os

    data_dir = Path(os.environ.get("DRIFT_DATA_DIR", "data"))
    serve(Queue(data_dir / "queue.db"), ProjectStore(data_dir), worker_id=os.environ.get("DRIFT_WORKER_ID", "worker-1"))

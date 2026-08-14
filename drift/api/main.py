"""FastAPI control plane + dashboard serving.

Submit a commit, poll the durable queue, and read the resulting assets and
graph. The heavy lifting happens in the worker, which leases jobs and runs the
drift engine; this service only enqueues and reports.

When the dashboard is built (apps/web/dist), this app also serves it at "/",
so one URL is both the API and the working UI.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..compiler import compile_graph
from ..orbit import DEFAULT_HANDLE, ORBIT_TEMPLATE, PARAM_HANDLE
from .queue import Queue
from .storage import ProjectStore

DATA_DIR = Path(os.environ.get("DRIFT_DATA_DIR", "data"))

app = FastAPI(title="drift", version="1.0.0")
queue = Queue(DATA_DIR / "queue.db")
store = ProjectStore(DATA_DIR)

api = APIRouter(prefix="/api")


class Commit(BaseModel):
    brief: str
    product: str
    handle: str = DEFAULT_HANDLE
    submission_key: str | None = None


def _hydrate(job: dict) -> dict:
    for field in ("payload", "result"):
        if job.get(field):
            job[field] = json.loads(job[field])
    return job


@api.post("/commit")
def commit(body: Commit):
    store.write_sources(body.brief, body.product)
    job_id, created = queue.submit(
        {"handle": body.handle},
        submission_key=body.submission_key,
    )
    return {"job_id": job_id, "created": created}


@api.get("/jobs")
def jobs():
    return [_hydrate(j) for j in queue.list()]


@api.get("/jobs/{job_id}")
def job(job_id: str):
    row = queue.get(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _hydrate(row)


@api.get("/stats")
def stats():
    return queue.stats()


@api.get("/graph")
def graph():
    compiled = compile_graph(ORBIT_TEMPLATE, parameters={PARAM_HANDLE: DEFAULT_HANDLE})
    nodes = [
        {
            "key": n.stable_key,
            "type": str(n.node_type),
            "label": n.label,
            "inputs": [slot.from_key for slot in n.inputs],
        }
        for n in compiled.nodes
    ]
    return {
        "template": compiled.template_key,
        "order": list(compiled.topological_order),
        "nodes": nodes,
    }


@api.get("/assets")
def assets():
    return store.assets()


@api.get("/health")
def health():
    return {"ok": True, "stats": queue.stats()}


app.include_router(api)
app.mount("/files", StaticFiles(directory=store.content), name="files")

# Serve the built dashboard at "/" so the live URL is a working UI, not JSON.
WEB_DIR = Path(
    os.environ.get(
        "DRIFT_WEB_DIR",
        str(Path(__file__).resolve().parents[2] / "apps" / "web" / "dist"),
    )
)
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")

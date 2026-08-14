<div align="center">

&nbsp;

[![Live site](https://img.shields.io/badge/●_live-drift--build.vercel.app-34d399)](https://drift-build.vercel.app)
[![GitHub](https://img.shields.io/badge/repo-subheeksh5599%2Fdrift-14151a)](https://github.com/subheeksh5599/drift)
[![License: MIT](https://img.shields.io/badge/license-MIT-34d399.svg)](LICENSE)
![Tests](https://img.shields.io/badge/tests-44%20passing-3fb950)
![Domain](https://img.shields.io/badge/domain-pure%20Python%20·%20stdlib-1f1f23)
![Media](https://img.shields.io/badge/media-HTML%2BChrome%20·%20ffmpeg%20·%20free%2C%20no%20API%20key-1f1f23)
![API](https://img.shields.io/badge/api-FastAPI%20·%20SQLite-1f1f23)

### A build system for a creator's content pipeline. Prove what changed, rebuild only what's stale.

Every title, caption, tag, post, poster, keyframe, narration and delivery video descends from one brief and one product reference. Edit the brief and everything downstream silently drifts stale. Drift treats that pipeline as a dependency graph — every asset content-addressed from its recipe and its exact inputs — so it can prove which assets are stale and rebuild only those, then re-verify the result from disk.

### ▶ Live — landing at **[drift-build.vercel.app](https://drift-build.vercel.app)**, full system in this repo

**[ Live site ↗ ](https://drift-build.vercel.app)** · **[ Repo ↗ ](https://github.com/subheeksh5599/drift)** · **[ Architecture ↓ ](#architecture)** · **[ Media (free, no API key) ↓ ](#media-generation--free-no-api-key)** · **[ Run it locally ↓ ](#run-it-locally)**

Built for the **Social Media Automation Hackathon**. MIT licensed.

</div>

---

## Table of contents

- [See it in one command](#-see-it-in-one-command)
- [The problem Drift solves](#the-problem-drift-solves)
- [How Drift works](#how-drift-works)
  - [1 · Compile](#1--compile)
  - [2 · Fingerprint](#2--fingerprint)
  - [3 · Impact](#3--impact)
  - [4 · Build](#4--build)
  - [5 · Verify](#5--verify)
- [The 18-node graph](#the-18-node-graph)
- [Architecture](#architecture)
  - [Component by component](#component-by-component)
- [Engineering decisions — the hard problems](#engineering-decisions--the-hard-problems)
- [Media generation — free, no API key](#media-generation--free-no-api-key)
- [What's real vs pending — the honesty table](#whats-real-vs-pending--the-honesty-table)
- [Tests](#tests)
- [Run it locally](#run-it-locally)
- [Configuration](#configuration)
- [Deploy](#deploy)
- [Project layout](#project-layout)
- [Tech stack](#tech-stack)
- [Roadmap](#roadmap)
- [License](#license)

---

## ▶ See it in one command

```bash
git clone https://github.com/subheeksh5599/drift.git && cd drift
uv sync --extra dev

uv run python -m drift.cli build demo/content     # 18 rebuild / 0 reuse
uv run python -m drift.cli build demo/content     # 0 rebuild / 18 reuse
uv run python -m drift.cli build demo/content --handle @newhandle  # 2 rebuild / 16 reuse
uv run python -m drift.cli verify demo/content    # OK — every asset re-hashes
```

`demo/content/out/` now holds real generated media: `image.poster.png`,
`transform.cutout.png`, three `image.keyframe.*.png`, `audio.narration.wav`,
and `compose.delivery.mp4` — all reproducible from the two source files, all
re-verifiable from disk.

---

## The problem Drift solves

A creator's content is a hidden dependency graph. Today:

- **Every asset is edited by hand** — title, description, tags, captions, posts, thumbnails, clips
- **A one-line edit silently invalidates everything** — change the brief and nothing tells you which posts are now stale
- **No proof of what changed** — schedulers will publish the stale assets for you
- **Rebuilds are all-or-nothing** — re-generate everything, or risk shipping one stale asset
- **No verifiable release** — nothing confirms what a build actually produced

Existing tools are either schedulers (publish, don't prove) or template engines (no dependency tracking). Drift treats the pipeline as a content-addressed build graph, so a source edit has a *provable* blast radius and a *verifiable* result.

---

## How Drift works

### 1 · Compile

A template + parameters compile deterministically into an immutable graph. Cycles, duplicate keys, self-edges and unknown dependencies are rejected.

### 2 · Fingerprint

Every node's identity is SHA-256 over a canonical (JCS / RFC 8785) encoding of its recipe and its exact input hashes. Floats are rejected so a hash can never depend on binary rounding.

### 3 · Impact

Walking the graph topologically, each node either passes a reuse proof or is marked rebuild. A node that rebuilds advertises a `pending:` placeholder, so the invalidation cascades to its descendants. Reasons distinguish "my own spec changed" from "something upstream changed".

### 4 · Build

Only the stale nodes regenerate. Before trusting a reuse, the on-disk bytes are re-hashed and compared — a tampered file is regenerated, never trusted. Text renders deterministically; images render as HTML via headless Chrome; audio/video via ffmpeg.

### 5 · Verify

A manifest binds every asset's output hash. `verify` re-reads every file from disk and re-hashes it. Change one byte — any asset or the manifest itself — and it fails.

---

## The 18-node graph

Two sources → nine text descendants → seven generated media assets:

```
source.brief ─┬─ plan.shots ─┬─ image.keyframe.01 ─┐
              ├─ title ──────┼─ image.keyframe.02 ─┼─ compose.delivery
              ├─ description ├─ image.keyframe.03 ─┘      (mp4)
              ├─ tags ───────┼─ audio.narration ─────────┘
              ├─ thumbnail_caption
              ├─ caption.x ── post.x     (handle bound)
              └─ caption.linkedin ─ post.linkedin (handle bound)

source.product ─┬─ image.poster
                └─ transform.cutout
```

The `handle` parameter is **bound** into exactly two nodes. Change it and two nodes rebuild; change the brief and everything but the product-only cutout rebuilds. The blast radius falls out of the fingerprint algorithm — it is not special-cased.

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   dashboard  │────▶│  FastAPI     │────▶│  SQLite queue    │
│  (Vite/React)│     │  control     │     │  claim/heartbeat │
│              │     │  plane       │     │  idempotent      │
└──────────────┘     └──────┬───────┘     └────────┬─────────┘
                            │                      │
                            ▼                      ▼
                     ┌──────────────┐     ┌──────────────────┐
                     │   worker     │────▶│  drift engine    │
                     │  (lease→gen) │     │  compile→impact  │
                     │              │     │  →build→verify   │
                     └──────┬───────┘     └────────┬─────────┘
                            │                      │
                            ▼                      ▼
                     ┌──────────────┐     ┌──────────────────┐
                     │  media infra │     │  HTML+Chrome     │
                     │  render.py   │────▶│  (images)        │
                     │              │     │  ffmpeg (av)     │
                     └──────────────┘     └──────────────────┘
```

### Component by component

| Component | Technology | Responsibility |
|---|---|---|
| `drift/` (domain) | pure Python, stdlib | compiler, JCS+SHA-256 fingerprinting, reuse proof, impact — zero I/O |
| `drift/infra/` | HTML + headless Chrome, ffmpeg | deterministic media generation |
| `drift/api/` | FastAPI, SQLite | control plane + durable queue (atomic claim, lease+heartbeat, idempotent submit, retry) |
| `drift/api/worker.py` | Python | separate process — lease a job, run the engine, heartbeat, complete |
| `apps/web/` | Vite + React | dashboard — commit a build, watch the queue, inspect assets |
| `site/` | static HTML | landing page |

---

## Engineering decisions — the hard problems

**1. The handle must be a bound parameter, not source text.** If the handle lived in the brief, changing it would cascade through all 18 nodes. Bound into only `post.x` and `post.linkedin`, a handle edit rebuilds 2 — proven by test, never special-cased.

**2. Reuse must re-hash disk bytes.** A reuse candidate that trusts `state.json` would bake a tampered file into the next manifest as legitimate. The build re-hashes the on-disk bytes before reuse; anything that diverged is regenerated.

**3. `verify` must pick the latest manifest by `created_at`, not filename.** Build ids are random hex, so filename order is meaningless. The manifest records its own timestamp, and `verify` sorts by it.

**4. Media must be deterministic to stay content-addressed.** A generative model would render different bytes per run, breaking fingerprinting. HTML + headless Chrome renders identical markup to identical bytes — so images are a pure function of the source, same as text.

**5. Postgres → SQLite.** Same claim/heartbeat/idempotency semantics (`BEGIN IMMEDIATE` for atomic claim), but zero external service — a judge can clone and run it with no database to spin up.

**6. Mixed-size frames need scale+pad before concat.** The poster is portrait, the keyframes landscape. ffmpeg's `concat` filter requires identical dimensions, so every frame is normalized to a 1280×720 canvas first.

---

## Media generation — free, no API key

Every media asset is generated without a paid model, a GPU, or an API key:

| Asset | How it's made | Cost |
|---|---|---|
| Poster, cutout, keyframes | HTML/CSS/SVG rendered by headless Chrome | free, deterministic, no key |
| Narration (voice) | ffmpeg `flite` TTS (offline), or a deterministic synthesized track | free, no key |
| Narration (optional upgrade) | Kyutai TTS over an OpenAI-compatible endpoint, when `DRIFT_TTS_URL` is set | needs a host, off by default |
| Delivery video | ffmpeg (keyframes + narration muxed) | free, deterministic |

This is the point, not a limitation: because generation is deterministic, every
byte is a pure function of the source and can be content-addressed and
re-verified. A generative-model provider plugs into the same `render.py` seam
without touching the graph.

---

## What's real vs pending — the honesty table

| Capability | Status | Detail |
|---|---|---|
| Graph compilation + topo order | ✅ Real | cycle/dupe/self-edge rejection tested |
| Content-addressed fingerprints | ✅ Real | JCS + SHA-256, floats rejected |
| Reuse proof + impact engine | ✅ Real | cascade + blast-radius tested |
| Text generation | ✅ Real | template / first-line / hashtag / shot-plan recipes |
| Image generation | ✅ Real | HTML + headless Chrome, free, no API key |
| Audio generation | ✅ Real | flite TTS / synthesized track, free, no key |
| Video generation | ✅ Real | ffmpeg mux, free |
| Release manifest + verify | ✅ Real | tamper / missing-file / manifest-tamper tested |
| Durable queue + worker | ✅ Real | claim/heartbeat/idempotency/retry tested |
| LLM copy generation | ⚠️ Not built | the generator seam it plugs into, env-gated |
| Hosted TTS (Kyutai / ElevenLabs) | ⚠️ Optional | wired, off until a key/endpoint is provided |

---

## Tests

44 tests passing — impact, build, orbit media, generation, compiler, queue, and CLI end-to-end.

```bash
uv run pytest -q
# 44 passed
```

The orbit tests assert the full media build end-to-end: 18 nodes, 2-rebuild handle blast radius, deterministic poster bytes, a real mp4 (`ffprobe`-verified), and a clean `verify`.

---

## Run it locally

```bash
git clone https://github.com/subheeksh5599/drift.git && cd drift
uv sync --extra dev

# CLI (the core)
uv run python -m drift.cli plan demo/content
uv run python -m drift.cli build demo/content
uv run python -m drift.cli verify demo/content
uv run python -m drift.cli report demo/content

# Full stack: API + worker + dashboard
DRIFT_DATA_DIR=data uv run uvicorn drift.api.main:app --port 8787     # terminal 1
DRIFT_DATA_DIR=data uv run python -m drift.api.worker                 # terminal 2
cd apps/web && npm install && npm run dev                            # terminal 3
```

Open `http://localhost:5173`, commit a brief, and watch an 18-node media build flow through the queue.

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| `DRIFT_DATA_DIR` | API/worker runtime dir (queue + content) | `data` |
| `DRIFT_TTS_URL` | OpenAI-compatible TTS endpoint (Kyutai) | unset → flite/tone |
| `DRIFT_TTS_KEY` | bearer key for the TTS endpoint | unset |
| `DRIFT_TTS_MODEL` | TTS model name | `kyutai` |
| `DRIFT_TTS_VOICE` | TTS voice | `default` |
| `DRIFT_WORKER_ID` | worker id for lease ownership | `worker-1` |

---

## Deploy

```bash
# API
DRIFT_DATA_DIR=/opt/drift/data uvicorn drift.api.main:app --host 0.0.0.0 --port 8787

# Worker
DRIFT_DATA_DIR=/opt/drift/data python -m drift.api.worker

# Dashboard + landing are static — serve via any static host (Vercel, nginx)
```

The landing is live at [drift-build.vercel.app](https://drift-build.vercel.app); the API + worker run on a persistent host (the repo ships everything needed for a single-box deploy).

---

## Project layout

```
drift/
├── drift/
│   ├── canonical.py      # JCS canonical JSON + SHA-256
│   ├── types.py          # graph + node types
│   ├── enums.py          # node types, decisions, reason codes
│   ├── compiler.py       # template → immutable graph
│   ├── fingerprint.py    # node fingerprints + pending placeholder
│   ├── impact.py         # reuse proof + impact engine
│   ├── orbit.py          # the 18-node launch graph
│   ├── generation.py     # deterministic text recipes
│   ├── build.py          # build orchestration (text + media)
│   ├── manifest.py       # manifest + release verification
│   ├── state.py          # node cache state
│   ├── infra/            # images.py (HTML+Chrome), audio.py, video.py (ffmpeg), render.py
│   ├── api/              # queue.py (SQLite queue), storage.py, main.py, worker.py
│   └── cli.py            # plan / build / verify / report
├── apps/web/             # Vite + React dashboard
├── site/                 # landing page
├── demo/content/         # brief.txt + product.txt (the real sources)
└── tests/                # 44 tests
```

---

## Tech stack

| Layer | Technology |
|---|---|
| Domain | Python 3.11+, stdlib only |
| Media | HTML/CSS/SVG + headless Chrome (images), ffmpeg (audio/video) |
| Control plane | FastAPI |
| Queue | SQLite (WAL, atomic claim) |
| Worker | Python, lease + heartbeat |
| Dashboard | Vite, React 18 |
| Landing | static HTML |

---

## Roadmap

- **LLM copy generation** — plug a text model into the generation seam
- **Hosted TTS + image providers** — swap the deterministic backends for a paid API via the same seam
- **Multi-project support** — one queue, many content directories
- **Postgres backend** — drop-in for the SQLite queue when a shared box is needed
- **Webhooks** — notify schedulers which assets changed after a build

---

## License

MIT — built for the Social Media Automation Hackathon, August 2026.

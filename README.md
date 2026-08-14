# DRIFT

![tests](https://img.shields.io/badge/tests-44%20passing-34d399)
![domain](https://img.shields.io/badge/domain-pure%20Python%20·%20zero%20I%2FO-14151a)
![media](https://img.shields.io/badge/media-HTML%20%2B%20Chrome%20%2B%20ffmpeg-14151a)
![api](https://img.shields.io/badge/api-FastAPI%20%2B%20SQLite-14151a)
![license](https://img.shields.io/badge/license-MIT-34d399.svg)

### A build system for a creator's content pipeline — prove what changed, rebuild only what is stale.

A creator's title, description, tags, captions, posts, poster, keyframes,
narration and delivery video all descend from two sources — a brief and a
product reference. Edit the brief and everything downstream silently drifts
stale. Drift treats that pipeline as a dependency graph: every asset is
content-addressed from its recipe and its exact inputs, so the system can
prove which assets are stale and rebuild only those — then re-verify the
result from disk.

It ships as a CLI, a FastAPI control plane with a durable job queue, a
separate worker, and a dashboard — the same architecture as any production
build pipeline, in one repo.

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

The `handle` parameter is **bound** into exactly two nodes (the posts). Change
it and two nodes rebuild; change the brief and everything but the product-only
cutout rebuilds. The blast radius is not special-cased — it falls out of the
fingerprint algorithm.

```
$ drift build demo/content
build 4bd83c5cf09b: 18 rebuild / 0 reuse / 0 blocked

$ drift build demo/content --handle @newhandle
build a97745bffcdc: 2 rebuild / 16 reuse / 0 blocked
```

---

## Proof — nothing here is a mockup

Every asset above is a real file with real bytes. Run it yourself:

```bash
uv sync --extra dev
uv run python -m drift.cli build demo/content     # 18 rebuild / 0 reuse
uv run python -m drift.cli build demo/content     # 0 rebuild / 18 reuse
uv run python -m drift.cli build demo/content --handle @newhandle  # 2 rebuild / 16 reuse
uv run python -m drift.cli verify demo/content    # OK — every asset re-hashes
```

`demo/content/out/` contains real generated media: `image.poster.png`,
`transform.cutout.png`, three `image.keyframe.*.png` (each authored as HTML/CSS
and rendered by headless Chrome), `audio.narration.wav` (ffmpeg — the `flite`
TTS filter when this build has it, otherwise a deterministic synthesized
track, or a Kyutai TTS endpoint when `DRIFT_TTS_URL` is set), and
`compose.delivery.mp4` (ffmpeg, the keyframes + narration muxed). No model
call and no randomness — every byte is a pure function of the source, which is
exactly why it can be content-addressed and re-verified.

Tamper with one file and `verify` catches it:

```
$ echo TAMPERED > demo/content/out/tags.txt
$ uv run python -m drift.cli verify demo/content
verify: FAILED
  - tags: hash mismatch (out/tags.txt)
```

---

## Architecture

| Layer | What it is |
|---|---|
| `drift/` (domain) | Pure Python graph engine — compiler, JCS+SHA-256 fingerprinting, reuse proof, impact. Zero I/O, stdlib only. |
| `drift/infra/` | Deterministic media generation — images as HTML+headless Chrome, audio/video via ffmpeg. |
| `drift/api/` | FastAPI control plane + a SQLite durable queue (atomic claim, lease + heartbeat, idempotent submit, retry). |
| `drift/api/worker.py` | The worker process — leases a job, runs the engine, heartbeats, completes. |
| `apps/web/` | Vite + React dashboard — commit a build, watch the queue, inspect the assets. |

Run the whole stack:

```bash
# terminal 1 — control plane
DRIFT_DATA_DIR=data uv run uvicorn drift.api.main:app --port 8787

# terminal 2 — worker
DRIFT_DATA_DIR=data uv run python -m drift.api.worker

# terminal 3 — dashboard
cd apps/web && npm install && npm run dev
```

Open `http://localhost:5173`, commit a brief, and watch a real 18-node media
build flow through the queue.

---

## How it works

1. **Compile** — a template + parameters compile deterministically into an
   immutable graph. Cycles, duplicate keys, self-edges and unknown deps are
   rejected.
2. **Fingerprint** — a node's identity is SHA-256 over a canonical (JCS /
   RFC 8785) encoding of its recipe and exact input hashes.
3. **Impact** — walking topologically, each node passes a reuse proof or is
   marked rebuild. A rebuilt node advertises a `pending:` placeholder so the
   invalidation cascades. Reasons distinguish "my spec changed" from "upstream
   changed".
4. **Build** — only stale nodes regenerate. Before trusting a reuse, the
   on-disk bytes are re-hashed and compared — a tampered file is regenerated,
   never trusted.
5. **Verify** — a manifest binds every asset's hash; `verify` re-reads every
   file from disk and re-hashes it.

---

## Honest status

| Capability | Status |
|---|---|
| Graph compilation + topo order | Real. Cycle/dupe/self-edge rejection tested. |
| Content-addressed fingerprints | Real. JCS + SHA-256, floats rejected. |
| Reuse proof + impact engine | Real. Cascade + blast-radius tested. |
| Text generation | Real. Deterministic template/first-line/hashtag/shot-plan recipes. |
| Image generation | Real. Poster, cutout, keyframes as HTML/CSS rendered by headless Chrome — deterministic, no model. |
| Audio generation | Real. Narration via ffmpeg (`flite` TTS when present, else a synthesized track). |
| Video generation | Real. Delivery mp4 via ffmpeg (keyframes + narration muxed). |
| Release manifest + verify | Real. Tamper + missing-file + manifest-tamper detection tested. |
| Durable queue + worker | Real. Claim/heartbeat/idempotency/retry tested. |
| LLM generation (AI copy) | Not built — the generator is the seam it plugs into, env-gated. |

---

## Project layout

```
drift/
  canonical.py      # JCS canonical JSON + SHA-256
  types.py          # graph + node types
  enums.py          # node types, decisions, reason codes
  compiler.py       # template -> immutable graph
  fingerprint.py    # node fingerprints + pending placeholder
  impact.py         # reuse proof + impact engine
  orbit.py          # the 18-node launch graph
  generation.py     # deterministic text recipes
  build.py          # build orchestration (text + media)
  manifest.py       # manifest + release verification
  state.py          # node cache state
  infra/            # images.py (HTML + Chrome), audio.py, video.py (ffmpeg), render.py
  api/              # queue.py (SQLite durable queue), storage.py, main.py, worker.py
  cli.py            # plan / build / verify / report
apps/web/           # Vite + React dashboard
demo/content/       # brief.txt + product.txt (the real sources)
tests/              # 44 tests across impact, build, orbit, generation, queue, cli
```

## License

MIT

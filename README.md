# DRIFT

![tests](https://img.shields.io/badge/tests-35%20passing-34d399)
![pure](https://img.shields.io/badge/domain-pure%20Python%20·%20zero%20I%2FO-14151a)
![std](https://img.shields.io/badge/deps-standard%20library%20only-14151a)
![license](https://img.shields.io/badge/license-MIT-34d399.svg)

### A build system for a creator's content pipeline — prove what changed, rebuild only what is stale.

Every piece of content a creator ships is derived from a source: the title,
description, tags, thumbnail, captions, and per-platform posts all descend from
one brief. When you edit the brief, everything downstream silently drifts stale
and you fix each one by hand. Drift treats that pipeline as a dependency graph —
every asset content-addressed from its recipe and its exact inputs — so it can
prove which assets are stale and rebuild only those.

---

## ▶ The two scenarios

**Edit the source → the cascade is real.**

```
$ drift build demo/content
build fb4e04b5e857: 9 rebuild / 0 reuse / 0 blocked
  rebuilt  source.brief
  rebuilt  title
  rebuilt  description
  ... (all 8 derived assets)
```

**Edit only the handle → only the posts rebuild, 7 assets survive.**

```
$ drift build demo/content --handle @newhandle
build a97745bffcdc: 2 rebuild / 7 reuse / 0 blocked
  rebuilt  post.x
  rebuilt  post.linkedin
  reused   source.brief
  reused   title
  reused   description
  reused   tags
  reused   thumbnail_caption
  reused   caption.x
  reused   caption.linkedin
```

The handle is a **bound parameter** — it is bound into exactly two nodes, so a
handle change can only invalidate those two. That is the whole claim, and it
falls out of the fingerprint algorithm rather than being special-cased.

---

## Proof — nothing here is a mockup

Every number above came out of a real run against a real file. Run it yourself:

```bash
uv sync --extra dev
uv run python -m drift.cli build demo/content        # 9 rebuild / 0 reuse
uv run python -m drift.cli build demo/content        # 0 rebuild / 9 reuse
uv run python -m drift.cli build demo/content --handle @newhandle   # 2 rebuild / 7 reuse
uv run python -m drift.cli verify demo/content       # OK — every asset re-hashes
```

Tamper with one generated file and `verify` catches it:

```
$ echo TAMPERED > demo/content/out/tags.txt
$ uv run python -m drift.cli verify demo/content
verify: FAILED
  - tags: hash mismatch (out/tags.txt)
```

Change one byte of the manifest and `verify` catches that too — the manifest is
bound by its own SHA-256.

---

## How it works

1. **Compile** — a template + parameters compile deterministically into an
   immutable graph. Cycles, duplicate keys, self-edges and unknown dependencies
   are rejected.
2. **Fingerprint** — every node's identity is SHA-256 over a canonical (JCS /
   RFC 8785) encoding of its recipe and its exact input hashes. Floats are
   rejected so a hash can never depend on binary rounding.
3. **Impact** — walking the graph in topological order, each node either passes
   a reuse proof or is marked rebuild. A node that rebuilds advertises a
   `pending:` placeholder, so the invalidation cascades to its descendants.
   Reasons distinguish "my own spec changed" from "something upstream changed".
4. **Build** — only the stale nodes regenerate. The post-build state records
   every node's *real* fingerprint from its *real* output hash.
5. **Verify** — a manifest binds every asset's output hash; `verify` re-reads
   every file from disk and re-hashes it.

---

## Honest status

| Capability | Status |
|---|---|
| Deterministic graph compilation | Real. Topological order, cycle/dupe/self-edge rejection. |
| Content-addressed fingerprints | Real. JCS + SHA-256, floats rejected, tested. |
| Reuse proof + impact engine | Real. Cascade and blast-radius scenarios tested. |
| Build — regenerate only stale assets | Real. 2/7 on a handle edit, measured. |
| Release manifest + `verify` | Real. Tamper and missing-file detection tested. |
| Text generation (title, posts, captions) | Real. Deterministic template render. |
| Hashtag extraction + platform limits | Real. Tags derived from the brief; posts truncated to per-network char limits. |
| Binary assets (clips, thumbnails via ffmpeg) | Not built. The generator is a seam this plugs into. |
| LLM generation (AI copy) | Not built. Same seam; env-gated, no key hardcoded. |
| Web UI | Not built. The CLI is the product today. |

---

## Run it locally

```bash
uv sync --extra dev
uv run python -m drift.cli plan demo/content      # predict, touch nothing
uv run python -m drift.cli build demo/content     # rebuild stale assets
uv run python -m drift.cli verify demo/content    # re-hash everything
uv run python -m drift.cli report demo/content    # provenance receipt
uv run pytest                                     # 35 tests
```

## Project layout

```
drift/
  canonical.py     # JCS canonical JSON + SHA-256
  types.py         # graph + node types
  compiler.py      # template -> immutable graph
  fingerprint.py   # node fingerprints + pending placeholder
  impact.py        # reuse proof + impact engine
  generation.py    # deterministic asset rendering
  build.py         # build orchestration
  manifest.py      # manifest + release verification
  state.py         # node cache state (load/save)
  demo_graph.py    # the creator pipeline template
  cli.py           # plan / build / verify
demo/
  content/brief.txt  # the real source file the CLI hashes
tests/
  test_impact.py     # compiler + impact scenarios
  test_build.py      # build round-trip + verify + tamper detection
```

## License

MIT

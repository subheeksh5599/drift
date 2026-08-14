# DRIFT

![tests](https://img.shields.io/badge/tests-22%20passing-34d399)
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

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

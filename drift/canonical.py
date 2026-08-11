"""Deterministic content addressing (JCS / RFC 8785).

Every hash Drift compares — node fingerprints, graph hashes, plan hashes — is
SHA-256 over a canonical JSON encoding. Canonical means: UTF-8, NFC-normalized
strings, object keys sorted by UTF-16 code unit, a stable number form, and
preserved array order. Two equal structures always hash identically no matter
how a program serialized them.

Floats are rejected in hashed payloads: binary rounding differs across
runtimes, so a float would make the same logical value hash differently.
Counts and dimensions travel as ints, money and measured decimals as strings.
"""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from typing import TypeAlias

JsonValue: TypeAlias = "None | bool | int | float | str | list[JsonValue] | dict[str, JsonValue]"


class CanonicalizationError(ValueError):
    """A value cannot be canonicalized deterministically."""


def _serialize_string(value: str) -> str:
    # ensure_ascii=False emits only '"', '\\' and control chars escaped, with
    # the short forms preferred — exactly RFC 8785's requirement. NFC first.
    return json.dumps(unicodedata.normalize("NFC", value), ensure_ascii=False)


def _serialize_number(value: int | float) -> str:
    if isinstance(value, bool):  # bool is an int subclass; caught here for safety
        raise CanonicalizationError("bool reached number serialization")
    if isinstance(value, int):
        return str(value)
    if not math.isfinite(value):
        raise CanonicalizationError(f"non-finite number is not representable: {value!r}")
    # ECMAScript renders integral doubles without a fraction: 1.0 -> "1".
    if value.is_integer() and abs(value) < 1e21:
        return str(int(value))
    return repr(value)


def _utf16_sort_key(key: str) -> bytes:
    # JCS sorts keys by UTF-16 code unit, which differs from Python's code-point
    # ordering above the BMP. UTF-16BE bytes reproduce it exactly.
    return key.encode("utf-16-be")


def _serialize(value: JsonValue) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return _serialize_number(value)
    if isinstance(value, str):
        return _serialize_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_serialize(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value, key=_utf16_sort_key):
            if not isinstance(key, str):
                raise CanonicalizationError("object keys must be strings")
            parts.append(f"{_serialize_string(key)}:{_serialize(value[key])}")
        return "{" + ",".join(parts) + "}"
    raise CanonicalizationError(f"type is not canonicalizable: {type(value).__name__}")


def canonical_json(value: JsonValue) -> str:
    """Canonicalize to a JCS string. Deterministic for equal inputs by construction."""
    return _serialize(value)


def canonical_hash(value: JsonValue) -> str:
    """SHA-256 hex of the canonical form. This is what fingerprints and plan hashes are."""
    return hashlib.sha256(_serialize(value).encode("utf-8")).hexdigest()


def canonical_payload(value: JsonValue) -> JsonValue:
    """Reject floats so a hash can never depend on binary rounding."""

    def check(node: JsonValue, path: str) -> None:
        if node is None or isinstance(node, (bool, int, str)):
            return
        if isinstance(node, float):
            raise CanonicalizationError(
                f"float at {path or '<root>'} is not permitted in a hashed payload; "
                "carry decimals as strings"
            )
        if isinstance(node, list):
            for index, item in enumerate(node):
                check(item, f"{path}[{index}]")
            return
        if isinstance(node, dict):
            for key, item in node.items():
                check(item, f"{path}.{key}" if path else key)
            return
        raise CanonicalizationError(f"type at {path or '<root>'} is not JSON: {type(node).__name__}")

    check(value, "")
    return value

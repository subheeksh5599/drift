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

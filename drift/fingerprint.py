"""Node fingerprints.

A fingerprint identifies an executable recipe and its exact selected inputs —
not the nondeterministic bytes a generator happens to produce. Two nodes with
the same fingerprint would run the same operation over the same inputs, which
is precisely the condition that makes reuse safe.

What must NOT be included: build IDs, timestamps, database UUIDs, attempt
numbers. Any of those would make every fingerprint unique and destroy reuse.
"""

from __future__ import annotations

from .canonical import canonical_hash, canonical_payload
from .types import SCHEMA_VERSION, CompiledNode

PENDING_PREFIX = "pending:"


def pending_output_ref(proposed_fingerprint: str) -> str:
    """Mark an input whose producer will rebuild, so its output bytes do not
    exist yet. The placeholder embeds the producer's proposed fingerprint, so it
    differs from the previously selected asset hash and the invalidation
    propagates to descendants — exactly how a rebuild cascades."""
    return f"{PENDING_PREFIX}{proposed_fingerprint}"


def is_pending(output_ref: str | None) -> bool:
    return output_ref is not None and output_ref.startswith(PENDING_PREFIX)


def compute_fingerprint(
    node: CompiledNode,
    *,
    input_refs: dict[str, str | None],
    template_version: int,
) -> str:
    """Fingerprint one derived node.

    `input_refs` maps each declared input's producing node key to that node's
    selected output reference — a content hash for a real asset, or a pending
    placeholder when the producer will rebuild. Inputs are emitted in the node's
    declared slot order, never sorted: swapping two slots changes the operation.
    """
    ordered_inputs = [
        {
            "slot": slot.slot,
            "ordinal": slot.ordinal,
            "from": slot.from_key,
            "selected_output_hash": input_refs.get(slot.from_key),
        }
        for slot in node.inputs
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "node_type": str(node.node_type),
        "operation": node.operation,
        "ordered_inputs": ordered_inputs,
        "template_version": template_version,
    }
    return canonical_hash(canonical_payload(payload))


def compute_source_fingerprint(node: CompiledNode, *, content_hash: str) -> str:
    """A source has no upstream inputs, so its identity is the verified content
    it carries. `content_hash` must come from bytes the system hashed itself —
    never a client-supplied claim."""
    return canonical_hash(
        {
            "schema_version": SCHEMA_VERSION,
            "node_type": str(node.node_type),
            "stable_key": node.stable_key,
            "content_hash": content_hash,
            "operation": node.operation,
        }
    )

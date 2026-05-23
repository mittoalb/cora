"""Signature verification + signed-event-type registry.

Stage-1 design lock implementation for Candidate F (signed events) per
[[project_signed_events_design]]. Iteration 2 ships the verification
path and the closed registry of event types that must be signed at
write time; the `Signer` port lives next door at
`cora.infrastructure.ports.signing`.

No production signer adapter ships in this iteration. The verification
function works against any future adapter (Sigstore Fulcio, SPIFFE / SVID,
cloud KMS, local keystore) because the signature input is the same DSSE
PAE wrapper used by [[project_content_addressed_identity_design]] for
content hashing. One canonicalization profile, two consumers.

## Algorithm

EdDSA over Ed25519. Picked per Stage-0 corpus survey: modal across
modern attestation ecosystems (Sigstore, in-toto, SLSA, age, Tailscale),
smaller signatures (64 bytes) than RSA-2048 (256 bytes), faster sign
(~50us) and verify (~150us) than RSA at typical CORA append rates.

## Signature input

`PAE(payload_type, canonical_body_bytes(payload))`, computed via the
shared helper in `cora.infrastructure.content_hash`. The payloadType
URI binds the event type into the signature so a `CautionProposed`
signature can never collide with a `DecisionRegistered` signature even
when their bodies happen to serialize to the same bytes.

## What is NOT here

  - The `Signer` Protocol lives in `cora.infrastructure.ports.signing`.
  - Production signing adapters are deferred; iteration 3 lands one.
  - The verification function takes an explicit public-key resolver
    callable rather than depending on a kernel-wide registry. Resolvers
    are call-site-specific (read-time verify can use a different cache
    than write-time signing); composition stays explicit.
"""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from cora.infrastructure.content_hash import canonical_body_bytes, pae_bytes

EVENT_TYPE_PAYLOAD_TYPE_PREFIX = "application/vnd.cora."
EVENT_TYPE_PAYLOAD_TYPE_SUFFIX = "+json"


SIGNED_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "CautionProposed",
        "DecisionRegistered",
    }
)
"""Closed set of event-type names that MUST be signed at write time.

Initial set per [[project_signed_events_design]]:

  - `CautionProposed`: produced by CautionDrafter
    ([[project_caution_drafter_design]]); the drafter is an AI agent.
  - `DecisionRegistered`: produced by Agents (RunDebriefer per
    [[project_run_debrief_design]]) AND by humans. Per design lock the
    signing requirement applies only to the Agent-produced rows; the
    handler tier discriminates by checking `actor_id` against the Agent
    BC's stable-id rule before invoking `Signer.sign`. Human-actor
    `DecisionRegistered` rows are unsigned.

Future Agent-BC event types land here by default. Expansion to
human-actor events requires a deliberate design lock per the
scientific-data corpus verdict.
"""


def event_type_to_payload_type(event_type: str) -> str:
    """Map an event-type name to its payloadType URI.

    `"CautionProposed"` -> `"application/vnd.cora.caution-proposed+json"`.
    `"DecisionRegistered"` -> `"application/vnd.cora.decision-registered+json"`.

    Single source of truth shared between sign-side and verify-side so
    the PAE input is provably the same bytes on both paths.
    """
    kebab = _camel_to_kebab(event_type)
    return f"{EVENT_TYPE_PAYLOAD_TYPE_PREFIX}{kebab}{EVENT_TYPE_PAYLOAD_TYPE_SUFFIX}"


def _camel_to_kebab(name: str) -> str:
    """Convert CamelCase event-type names to kebab-case payloadType slugs.

    Internal helper. CORA event-type names are CamelCase by convention
    (`CautionProposed`, `DecisionRegistered`); payloadType URIs follow
    the IANA media-type kebab-case convention. Acronym-aware: insert
    a dash before an uppercase letter when the previous char is
    lowercase (CamelCase boundary) OR when the next char is lowercase
    and the previous char was uppercase (last-letter-of-acronym
    boundary). So `MCPSessionOpened` becomes `mcp-session-opened`,
    not `m-c-p-session-opened`.
    """
    if not name:
        return ""
    out: list[str] = [name[0].lower()]
    for i in range(1, len(name)):
        ch = name[i]
        prev = name[i - 1]
        nxt = name[i + 1] if i + 1 < len(name) else ""
        if ch.isupper() and (prev.islower() or (nxt != "" and nxt.islower())):
            out.append("-")
        out.append(ch.lower())
    return "".join(out)


class SignatureInvalidError(Exception):
    """The recorded signature does not verify against the recomputed bytes.

    Critical: surfaces tampering, schema-evolution-without-payloadType
    bump, or key compromise. Surfaces as HTTP 422 at API boundary
    (read-time verify mode) or HTTP 500 in internal audit paths.
    """

    def __init__(self, event_type: str, kid: str, detail: str = "") -> None:
        super().__init__(
            f"Signature invalid for event_type {event_type!r}, kid {kid!r}"
            + (f": {detail}" if detail else "")
        )
        self.event_type = event_type
        self.kid = kid
        self.detail = detail


class SignatureMissingError(Exception):
    """A signed-event-type row was read with no signature.

    Distinct from `SignatureInvalidError` so monitoring can distinguish
    "tampered" from "never signed" (the latter expected for pre-rollout
    events, suspicious for new events of a SIGNED_EVENT_TYPES type).
    """

    def __init__(self, event_type: str) -> None:
        super().__init__(f"Event {event_type!r} is in SIGNED_EVENT_TYPES but has no signature")
        self.event_type = event_type


async def verify_signature(
    *,
    event_type: str,
    payload: Mapping[str, Any],
    signature: bytes,
    kid: str,
    resolve_public_key: Callable[[str], Awaitable[bytes]],
) -> None:
    """Verify a signature over an event payload. Raise on failure.

    Recomputes the canonical-body-bytes from `payload` via the shared
    helper in `content_hash`, wraps in PAE with the payloadType derived
    from `event_type`, resolves the public key for `kid`, and verifies
    using Ed25519. Same bytes the signer signed; deterministic
    canonicalization profile guaranteed by the shared helper.

    `resolve_public_key` is an async callable taking the `kid` and
    returning the raw 32 bytes of the Ed25519 public key. Call-site
    chooses the resolver (in-memory cache for hot verify paths,
    JWKS-backed for federated paths, etc.).

    Raises:
      - `SignatureInvalidError`: signature does not verify
    """
    payload_type = event_type_to_payload_type(event_type)
    body_bytes = canonical_body_bytes(payload)
    pae = pae_bytes(payload_type, body_bytes)
    public_key_bytes = await resolve_public_key(kid)
    try:
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
    except ValueError as exc:
        raise SignatureInvalidError(event_type, kid, f"public key malformed: {exc}") from exc
    try:
        public_key.verify(signature, pae)
    except InvalidSignature as exc:
        raise SignatureInvalidError(event_type, kid) from exc


__all__ = [
    "EVENT_TYPE_PAYLOAD_TYPE_PREFIX",
    "EVENT_TYPE_PAYLOAD_TYPE_SUFFIX",
    "SIGNED_EVENT_TYPES",
    "SignatureInvalidError",
    "SignatureMissingError",
    "event_type_to_payload_type",
    "verify_signature",
]

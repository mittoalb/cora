-- Candidate F (signed events) schema substrate: nullable signature
-- columns on the events table.
--
-- Stage-1 design lock `project_signed_events_design`. Adds the two
-- columns the handler tier will populate when an AI-agent-produced
-- event from `SIGNED_EVENT_TYPES` lands. Iteration 3 ships ONLY the
-- columns; the handler-side signing wiring lands in a future
-- iteration (likely Caution BC first, then Decision BC for Agent-
-- produced rows).
--
-- Why nullable and undefaulted:
--
--   - `signature IS NULL` is the legitimate marker for pre-rollout
--     events (immortal per `project_immutability_guarantee`). The
--     forward-only migration policy forbids backfill; historical
--     events stay unsigned forever and that is the correct semantic.
--   - `signature IS NULL` is also the legitimate marker for human-
--     actor `DecisionRegistered` rows (per scientific-data corpus
--     verdict in `project_signed_events_research`: registry
--     attestation suffices for human events; signing is reserved
--     for AI-agent rows).
--   - Per design lock anti-hook: never enforces NOT NULL at the
--     table level. The per-event-type opt-in invariant lives in
--     `cora.infrastructure.signing.SIGNED_EVENT_TYPES`, enforced
--     at read time when `EventStore.read_stream(verify=True,
--     raise_on_missing_signature=True)`.
--
-- The CHECK constraint enforces both-null-or-both-set consistency:
-- a signature without its kid (or vice versa) is a write-side bug
-- the database catches at INSERT, before the row lands. Distinct
-- from "no signature at all" (both NULL) which is legitimate per
-- the design lock.
--
-- bytea vs text for the signature:
--
--   Ed25519 signatures are exactly 64 raw bytes per RFC 8032.
--   Storing bytea (not hex / not base64) keeps the row footprint
--   minimal and avoids encoding-round-trip risk between signer and
--   verifier. `Ed25519PublicKey.verify(signature, pae_bytes)` takes
--   raw bytes; the asyncpg bytea<->Python bytes round-trip is
--   lossless.
--
-- text for signature_kid:
--
--   `kid` is an opaque adapter-specific string (Sigstore Fulcio
--   cert serial, SPIFFE ID, KMS key resource name, JWKS key id).
--   Length varies by adapter; text is the unconstrained choice.
--   The verifier resolves kid -> public key bytes via an injectable
--   `resolve_public_key` callable; no constraints on kid format
--   live at the database layer.
--
-- No index on either column:
--
--   Verification is per-row (read an event, recompute PAE bytes,
--   verify against the stored signature using the resolved public
--   key). There is no "find all events signed by kid X" filter
--   query in the design. If audit dashboards later need that, a
--   `WHERE signature_kid = $1` filter can be added with a partial
--   index `WHERE signature_kid IS NOT NULL`.
--
-- No update to the `events_notify` trigger:
--
--   The notify payload is `(position, stream_type, stream_id,
--   event_type)`. Signature presence is not a routing concern;
--   subscribers that need to verify read the row, not the
--   notification payload.
--
-- Length constraints (defense-in-depth):
--
--   `events` is INSERT-only and immortal under
--   `project_forward_only_migrations`, so a buggy or compromised
--   adapter inserting multi-MB blobs would pollute the table
--   irreversibly. Constrain both columns to plausible sizes at
--   the schema layer:
--
--     - signature: exactly 64 bytes when non-NULL (Ed25519 raw
--       signature size per RFC 8032). If a future signing scheme
--       lands a different size, widen this constraint in a
--       follow-up migration alongside the design-lock revision.
--     - signature_kid: 1 to 256 chars when non-NULL. Empty string
--       is rejected (a kid with no resolvable value is meaningless
--       to the verifier); 256 chars accommodates Sigstore Fulcio
--       cert serials, SPIFFE IDs, and KMS resource names with
--       headroom.

ALTER TABLE events
    ADD COLUMN signature      BYTEA,
    ADD COLUMN signature_kid  TEXT;

ALTER TABLE events
    ADD CONSTRAINT events_signature_kid_consistency
        CHECK ((signature IS NULL) = (signature_kid IS NULL)),
    ADD CONSTRAINT events_signature_length
        CHECK (signature IS NULL OR octet_length(signature) = 64),
    ADD CONSTRAINT events_signature_kid_length
        CHECK (signature_kid IS NULL OR octet_length(signature_kid) BETWEEN 1 AND 256);

"""Data bounded context.

Owns the "what came out" side of every Run. Per BC map, two
aggregates eventually (`Dataset`, `Transfer`); first cut is just
`Dataset`, the logical research data product, with bulk referenced
by URI + sha256 checksum.

Independent track BC (no ISA analog). Cross-BC reads at registration
time:
  - `Run` (Track A): producing_run_id is the Run that produced the
    Dataset; existence-checked at registration (no status check).
  - `Subject` (Independent): subject_id is the Subject the Dataset
    is about; existence-checked at registration.
  - `Dataset` (recursive): each derived_from id is an upstream
    Dataset this one was derived from; each existence-checked.

What `Dataset` is NOT:
  - Not the bytes (those live at the URI; S3 / Globus / POSIX / etc.)
  - Not a substream entry (per-projection rows live in a future Run
    samples logbook with the dataset URI as a column)
  - Not a Transfer (separate aggregate, deferred to its own phase)

## Phase 7a/7b scope

Minimal Dataset: id + name + uri + checksum + byte_size + encoding
+ optional cross-refs + status (defaults `Registered`).

Three slices:
  - `register_dataset` (create-style; idempotency-wrapped; full
    cross-aggregate validation via DatasetRegistrationContext;
    rejects Discarded sources in derived_from per 7b tightening)
  - `discard_dataset` (Registered → Discarded terminal; strict-not-
    idempotent; free-form `reason: str` 1-500 chars; GDPR-shaped)
  - `get_dataset` (read side; fold-on-read; mirrors get_subject)

Archive / Verify / Move transitions defer until storage tiers /
re-checksum workflows ship.

## Standards alignment (post-survey, gate-review L3 + deferred-with-trigger)

  - PROV-O at API export boundary (deferred until first PROV
    consumer)
  - DataCite 4.7 metadata schema as export schema (deferred until
    cross-facility export ships)
  - RO-Crate 1.2 as packaging (deferred until cross-facility export)
  - FAIR Signposting at REST export (deferred-with-trigger: first
    license / citation / PROV graph endpoint)
  - In-domain `encoding` (schema.org / RO-Crate vocabulary) carries
    media_type + conforms_to: list of profile URIs; locked at L3 to
    avoid breaking change later. DataCite's export schema uses
    `format` which the export adapter would map to.
  - Croissant defer (ML-side; trigger = first ML-training export)
  - Zarr v3 defer (trigger = first cloud-native facility ingest)

Layout (mirrors every other BC):
    aggregates/dataset/      -- aggregate state, events union, evolver, read
    features/<verb>_dataset/ -- vertical slice: command/query + decider? + handler + route + tool
    wire.py                  -- DataHandlers bundle + wire_data(deps)
    routes.py                -- register_data_routes(app)
    tools.py                 -- register_data_tools(mcp, *, get_handlers)
"""

from cora.data.errors import UnauthorizedError
from cora.data.routes import register_data_routes
from cora.data.tools import register_data_tools
from cora.data.wire import DataHandlers, wire_data

__all__ = [
    "DataHandlers",
    "UnauthorizedError",
    "register_data_routes",
    "register_data_tools",
    "wire_data",
]

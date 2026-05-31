# Event corpus fixtures

Golden payload fixtures for the `test_upcaster_corpus` fitness function
at `tests/architecture/test_upcaster_corpus.py`.

## Layout

```
event_corpus/<bc>/<aggregate>/<event_type>_v<N>[_<variant>].json
```

Each JSON file is a self-describing record:

```json
{
  "event_type": "<wire discriminator the aggregate's from_stored matches>",
  "payload": { <raw payload dict as it would land in StoredEvent.payload> },
  "expected": {
    "class": "<dataclass name from the BC's <Aggregate>Event union>",
    "<field>": <expected value after upcasting>,
    ...
  }
}
```

The fitness function discovers every fixture under this tree, resolves
the BC's `from_stored` via the `_BC_REGISTRY` map at the top of the
test, builds a `StoredEvent` envelope around `payload`, calls
`from_stored`, and asserts the result matches `expected` field-by-field.

## When to add a fixture

Add a fixture whenever a `from_stored` arm exists purely to replay a
legacy `event_type` discriminator or a legacy payload shape (the
Marten / Axon canonical-rename pattern). The fixture freezes a
realistic pre-rename payload so the upcast path keeps being exercised
even when the property test that originally covered it gets refactored.

For greenfield aggregates that never shipped pre-rename, prefer the
inline-payload property tests at
`tests/unit/<bc>/test_<aggregate>_events_serialization_properties.py`.

## Currently covered

- `access/actor/actor_registered_v1.json` -- pre-PII-vault V1 (carries
  `name` + explicit `kind`); upcasts to V2 dropping `name`.
- `access/actor/actor_registered_v1_no_kind.json` -- oldest V1 shape
  with no `kind`; exercises the `HUMAN` fallback branch.
- `access/actor/actor_registered_v2.json` -- modern V2 shape (no
  `name`); locks the happy-path discriminator.

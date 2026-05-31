# Conventions

*Identifiers, units of measurement, personal data, schema-validated values, documentation.*

Cross-cutting shapes that recur in every BC. Each family below has one chosen pattern and a short list of anti-patterns that the codebase has settled on. Adopt the pattern when adding a field of that shape; deviate only with a reason.

## Identifiers

Every aggregate gets an opaque internal id at creation. External publication-quality identifiers (DOI, Handle, ORCID, ROR) are minted lazily, only when an outside system needs to cite the entity.

- **Internal id**: UUIDv7 produced by `IdGenerator` port. Carried on every event payload and used as the stream id. Stable for the lifetime of the aggregate, never reused.
- **External id slot**: nullable `external_id: str?` (or a typed `external_refs` map for entities that can carry several) on the aggregate, populated by a later transition event when the external mint succeeds.
- **No coupling**: domain logic never depends on the external id being present. A Run can complete, a Dataset can be archived, a Subject can be discharged without ever being assigned a DOI.

Per-entity scheme map below; the scheme is a docs and adapter concern, not a domain concern. The aggregate carries an opaque string and the namespace of the publishing system.

| Aggregate | External scheme | Authority | Notes |
| --- | --- | --- | --- |
| `data.dataset` | DataCite DOI | DataCite | Kernel 4.6 metadata profile |
| `subject.subject` | IGSN | IGSN through DataCite | Since 2022 an IGSN is a DataCite DOI |
| `equipment.asset` | PIDINST | DataCite or ePIC Handle | Scheme picked when the first asset is cited externally |
| `access.actor` | ORCID iD | ORCID | Separate registry, not a DOI |
| `decision.decision` | none today | n/a | Internal id sufficient until cross-system citation appears |

Cross-entity links between externally published entities use the publishing system's own relationship vocabulary at the export adapter (DataCite `relatedIdentifier`, PROV-O `wasDerivedFrom`). The in-domain reference stays a plain UUID.

**Anti-patterns:**

- Do not use an external identifier as the primary key. Mint timing slips, schemes get renamed, and the cost of changing an aggregate's identity is high.
- Do not block aggregate creation on external mint. A network failure on the mint side should never prevent a Subject from being registered or a Run from starting.
- Do not embed the scheme in the value (`"doi:10.1234/abc"`). Carry the namespace separately so the value stays opaque to the namespace.

## Units of measurement

Numeric fields whose meaning depends on a unit carry the unit as a three-field annotation on the declaring JSON Schema, not in the field name. The annotation is `{system, code, label?}`.

```json
{
  "type": "object",
  "properties": {
    "energy": {
      "type": "number", "minimum": 5.0, "maximum": 35.0,
      "unit": {"system": "udunits", "code": "keV"}
    },
    "exposure": {
      "type": "number", "minimum": 0,
      "unit": {"system": "udunits", "code": "ms", "label": "milliseconds"}
    },
    "start_position": {
      "type": "number",
      "unit": {"system": "udunits", "code": "mm"}
    }
  }
}
```

- **`system`**: namespace identifier; `udunits` for beamline-native fields, `ucum` for clinical, `qudt` for linked-data export, `iec61360` for Industry-4.0 partners. Closed allowlist enforced by `cora.infrastructure.json_schema_validation`.
- **`code`**: the unit token interpreted within `system`. Opaque to anyone outside that namespace.
- **`label`**: optional human display string for codes that are not self-explanatory.

The schema-declared unit is the canonical wire-and-storage unit. Deciders, events, projections, and API responses always carry the value in that exact unit. Conversion happens only at the edge: the NeXus writer adapter flattens to the single `units` string the file format expects; the EPICS reader adapter wraps the legacy `EGU` string back into the annotation shape on the way in; the UI display layer may convert to a per-user preferred unit when that table exists.

**Anti-patterns:**

- Do not put units in field names. `start_position`, not `start_position_mm`; `energy`, not `energy_kev`. The whole point of the annotation is to escape the lock-in that field suffixes create.
- Do not add a `display_unit` second slot on the schema. Display is a per-user concern at the UI edge, not a schema concern.
- Do not convert units inside deciders, evolvers, or projections. The domain ring carries one unit per field.
- Do not change the `system` or `code` of an existing field by editing the schema in place. Emit a new schema version and let downstream rebuild against it (the [forward-only migration policy](workflow.md) applies).

## Personal data

Personal data on Actors lives in a separate mutable `actor_profile` table, not in events. Events carry `actor_id` only. Erasure scrubs the row before deleting it (`UPDATE ... SET name = ''` then `DELETE`) so the dead-tuple bytes carry no PII before VACUUM.

- **Actor aggregate state** holds `id` and `is_active`; no `name`, no `email`. The event payloads carry the same fields.
- **`actor_profile` table** holds `actor_id PRIMARY KEY`, `name`, optional contact fields, `created_at`, `updated_at`. Written in the same transaction as `ActorRegistered`. The table has `FORCE ROW LEVEL SECURITY` enabled so even superuser sessions go through the policy.
- **Load path** left-joins `actor_profile` and falls back to `<deleted user>` when the row is absent.
- **`forget_actor` slice** scrubs-then-deletes the profile row and emits `ActorProfileForgotten(actor_id, occurred_at)` in a single transaction. The audit event carries no personal data.

The same pattern applies to any future field that may contain personal data: add it as a nullable column on `actor_profile`, or stand up a parallel vault table when the new field belongs to a different aggregate. The infrastructure is one table, not a key-management system.

**Anti-patterns:**

- Do not put personal data in event payloads. Events are immutable; personal data must be deletable.
- Do not encrypt-and-throw-away-the-key (the crypto-shredding pattern). Regulators increasingly treat encrypted personal data as still personal data, and the operational complexity is high for no real benefit when a simple delete is available.
- Do not assume free-text fields are safe from personal data. Reason strings on transition events may contain names or contact details by accident; convention is to either route the free-text through the vault or mark the field as may-contain-personal-data so future erasure tooling knows to check.

## Schema-validated values

One aggregate declares a JSON Schema; another aggregate carries a dict of values validated against it at write time. Two domain families share one implementation, with two deliberately distinct vocabularies.

| Family | Declarer | Carrier | Domain meaning |
| --- | --- | --- | --- |
| Settings | `capability.settings_schema` | `asset.settings` | Slow-moving equipment configuration: pixel offsets, motor calibration values, vendor-specific tuning |
| Parameters | `method.parameters_schema` | `plan.default_parameters` and `run.effective_parameters` | Per-experiment variables: energy, exposure, sample position |

The vocabularies are not interchangeable. "Settings" maps to PLC and SCADA vocabulary and lifecycle; "parameters" maps to recipe and process-control vocabulary. Operators expect both terms in their respective contexts; CORA keeps both.

The shared infrastructure lives in `cora.infrastructure.json_schema_validation` and exposes two functions:

- `validate_schema_declaration(schema, *, error_class)` runs on the declarer's write path. Rejects schemas that are missing or that have the wrong `$schema`, use a forbidden keyword (`$ref`, `oneOf`, `allOf`, conditionals), or fail to compile.
- `validate_values_against_schema(values, schema, *, error_class, no_schema_message)` runs on the carrier's write path.

Each BC keeps its own typed error class (`InvalidCapabilityParametersSchemaError`, `InvalidMethodParametersSchemaError`, `InvalidAssetSettingsError`, `InvalidPlanDefaultParametersError`, `InvalidRunParametersError`) and passes it into the shared validator. Each maps to HTTP 400 via the BC's own route. Different classes mean log aggregators can identify the source BC without parsing message text.

**Strict-by-default posture:** the carrier's validator follows a four-cell table that all instances share.

| schema | values | result |
| --- | --- | --- |
| absent | empty | accept (trivially valid) |
| absent | non-empty | reject with operator guidance |
| present | empty | accept (no required-field check at this layer) |
| present | non-empty | compile and validate; reject on first violation |

Operators wanting "this Capability or Method genuinely has no values to constrain" declare an empty `{}` schema explicitly. The implicit "no schema, anything goes" path is closed by design.

**Anti-patterns:**

- Do not inline schema validation in slices. Always go through the shared validator with a BC-specific error class.
- Do not let carriers fall back to "accept anything" when the declarer's schema is absent. The strict-by-default posture catches the common operator mistake of writing values before declaring how they should be shaped.
- Do not collapse the settings and parameters vocabularies into one name. They are two domain families that happen to share an implementation; the names carry the lifecycle distinction.
- Do not extend the JSON Schema subset to allow `$ref`, `oneOf`, `allOf`, or conditionals without adding the corresponding evolver and projection support. The constrained subset is what lets the declarer's schema be stored, evolved, and rebuilt deterministically.

**Forward-compatible discipline.** `capability.settings_schema` is the strongest candidate to travel between facilities once a publish-pull artifact registry lands. Authoring discipline today avoids a rename pass later. The rules are borrowed from Linux Device Tree bindings: describe the hardware, not the driver; close the schema; reserve namespace expansion slots.

- **Close the schema at every object level.** Set both `additionalProperties: false` and `unevaluatedProperties: false`. Unknown fields are a contract break, not a quiet extension point. A facility that pulls a foreign Capability must fail loudly on a property it does not recognize.
- **Vendor-prefix vendor-specific extensions only.** Properties shared across all instances of the equipment family (`encoder_resolution_deg`, `pixel_pitch_um`) stay generic. Properties that are vendor-specific go under a dotted vendor namespace (`aerotech.servo_gain`, `andor.read_mode`). The generic form is reserved for cross-vendor consensus; do not invent generic names that one vendor's quirk currently occupies.
- **Describe the hardware, not the driver.** Property descriptions name the physical quantity, range, and unit. They do not reference Python classes, EPICS PV names, Tango device URIs, ophyd-async Devices, or any other transport. The same schema must serve an APS-EPICS Capability and a MAX-IV-Tango Capability without edits.
- **Reserve `compatible` and `backend` as property names.** Do not use either name for unrelated purposes in current schemas. They are the documented expansion slots for future cross-facility Asset Integration Manifests.

These rules cost nothing at write time and apply equally to `method.parameters_schema` for the same reason.

## Documentation

Docstrings carry intent. Comments carry hidden constraints. Test names carry scenarios. Everything else is noise.

No emoji anywhere in source — comments, docstrings, log strings, error messages, `Field(description=...)`. Emoji in source is a documented LLM tell ([LLM Slop Taxonomy](https://github.com/nokusukun/sublime/blob/main/llm-slop-taxonomy.md) Cat 4.5 and 7.1) that accumulates as noise across reviews. Mirrors the no-em-dash rule applied to prose.

### Docstrings

Every public module, class, function, and method gets a docstring. Style is prose, not Sphinx.

- **One imperative summary line.** Single-line docstrings stay on one line: `"""Load and fold a Caution's event stream into current state."""`. End with a period.
- **Prose body when more is needed.** Blank line after the summary, then narrative paragraphs. Use Markdown subheaders (`## Section`) for distinct concerns.
- **Domain vocabulary matches the [glossary](glossary.md).** A slice handler is a handler, not an endpoint. An aggregate is an aggregate, not a model. An evolver is an evolver, not a reducer.
- **Cross-references**:
    - Backticks for in-module symbols: `` `ActorName` ``, `` `evolve()` ``.
    - Dotted path for cross-BC symbols: `` `cora.infrastructure.evolver.require_state` ``.
    - Wiki link only for design memos: `[[project_fold_cost_principles]]`.

**Role-type templates** (established by precedent; copy rather than improvise):

| Role | Module summary | Function summary |
| --- | --- | --- |
| Evolver | "Evolver: replay events to reconstruct `<Aggregate>` state." | `evolve()`: "Apply one event to the current state." / `fold()`: "Replay a stream of events from the empty initial state." |
| Read repo | "Read repository for the `<Aggregate>` aggregate." | `load_<aggregate>()`: "Load and fold a `<Aggregate>`'s event stream into current state." |
| Slice file header | "<role> for the `<slice>` slice." (one each in `route.py`, `tool.py`, `decider.py`, `handler.py`, `command.py`) | n/a |

**Anti-patterns:**

- Do not use `Args:` / `Returns:` / `Raises:` sections. Type annotations are the parameter contract; raised exceptions belong in prose when non-obvious.
- Do not restate the type signature in prose (`"""name (str): The name."""`).
- Do not write `>>>` doctest examples. CORA's tests are external.
- Do not name a phase, iteration, or audit (`Phase 5h`, `Iter B-3`, `DLM-A`, `audit-2026-05-20`) in a docstring. Those rot. The current code is what is true; phase ordering lives in `project_phase_plan.md` and git history. Name the precedent itself (`mirrors get_actor`), not the phase that shipped it.

### Comments

Default to none. Well-named identifiers carry WHAT.

Add a `#` comment only when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug, behavior that would surprise a reader. State the constraint, not the history.

**Anti-patterns:**

- Do not narrate WHAT the next line does (`# Set the replaced_by pointer`). The code says that.
- Do not annotate the current task, fix, or caller (`# added for X flow`, `# used by Y`, `# Phase 6i-c membership guard`). Git log and PR description are the right home.
- Do not leave dead-code markers (`# was`, `# previously`, `# old`). Delete the dead code.
- Do not leave `# TODO`, `# FIXME`, `# HACK` without an owner and a trigger. File an issue or drop it.
- Do not use `# noqa: <code>` without a trailing comment explaining the suppression.
- Do not draw section dividers (`# === STATE ===`). The role-typed file layout — one aggregate per file, one slice per directory — already provides navigation. ([antirez](https://antirez.com/news/124) defends "guide comments" as cognitive-load reduction for long single-purpose files; CORA's files don't reach that length.)

### Tests

Test names carry scenarios. Per-test docstrings stay rare.

- **`test_<subject>_<scenario>_<expectation>`** is the naming convention. Long is fine: `test_deactivate_with_none_state_always_raises_not_found`.
- **Property-based tests document the property**, not the test shape. The `@given` body is the test; the docstring is the invariant being verified.
- **Architecture tests document the rule, the rationale, and the exception.** They are the project's structural guardrails; future contributors need to know why each rule exists.
- **Fixture docstrings only when non-obvious.** Per-worker Postgres containers, kernel-construction sites, template-database cloning, and similar subtleties get one paragraph in `conftest.py`. Simple fixtures stay bare.

## Where each family is enforced

| Family | Domain entry point | Shared infrastructure |
| --- | --- | --- |
| Identifiers | `IdGenerator` port; per-aggregate `external_id` field | `cora.infrastructure.ids` |
| Units of measurement | declarer's JSON Schema; allowlist of `system` namespaces | `cora.infrastructure.json_schema_validation` |
| Personal data | `Actor` state; `profile` table | `cora.access.aggregates.actor.profile` |
| Schema-validated values | declarer's schema field; carrier's values field | `cora.infrastructure.json_schema_validation`, `cora.infrastructure.json_schema_subset` |
| Documentation | docstring on every public symbol; sparse `#` comments | [Glossary](glossary.md) for vocabulary |

For the deeper rules each family inherits from (event sourcing, value-object scope, field grouping), see [Modeling](modeling.md). For the read-side, idempotency, and cross-aggregate validation patterns, see [Patterns](patterns.md).

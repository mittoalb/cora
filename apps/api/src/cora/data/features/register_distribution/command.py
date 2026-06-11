"""The `RegisterDistribution` command, intent dataclass for this slice.

Carries everything the caller controls to register a new
materialized byte-copy of a logical Dataset at a storage Supply:
the cross-aggregate refs (`dataset_id` same-BC, `supply_id`
cross-BC), the addressing (`uri`, `access_protocol`), and the
byte-identical-copy invariants (`checksum`, `byte_size`,
`encoding`). The new Distribution id is server-allocated by the
handler from the IdGenerator port (matches every other
create-style slice).

"Register" rather than "define": the byte-copy exists in the world
already (the operator has it sitting at the URI inside the Supply
storage) and we are recording its existence. Same convention as
`register_dataset` / `register_supply` / `register_asset` /
`register_fixture`.

## Flat boundary, nested event payload

Per [[project-data-distribution-design]] L9: the REST + MCP
Pydantic boundary uses flat fields (`checksum_algorithm` +
`checksum_value`, `media_type` + `conforms_to`) for wire ergonomics.
The on-disk event payload uses nested objects mirroring
`DatasetRegistered`. This command object accepts the flat boundary
form; the decider reconstructs the nested form before event
emission.

## Strict-not-idempotent at the decider

Per L16: same-stream-id re-issue raises
`DistributionAlreadyExistsError`. No silent `[]` no-op. Cross-stream
`(dataset_id, supply_id, uri)` triple collision is NOT a decider
concern (writer-side swallow per L31).
"""

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class RegisterDistribution:
    """Register a new Distribution with the given metadata."""

    dataset_id: UUID
    supply_id: UUID
    uri: str
    checksum_algorithm: str
    checksum_value: str
    byte_size: int
    media_type: str
    access_protocol: str
    conforms_to: frozenset[str] = field(default_factory=frozenset[str])

"""State-vs-event consistency fitness for `RecipeExpansionRecorded`.

Anti-hook 15 of [[project-recipe-aggregate-design]] pins
`capability_id + capability_version` on the `RecipeExpansionRecorded`
payload as a denormalized snapshot of the Capability state at
expansion time. A future refactor that silently drops the denorm
would break audit-by-Capability read paths; this fitness keeps the
contract honest by asserting the event class declares the denorm
fields AND the to_payload arm carries them.

Runs at the unit tier against an in-memory construction of the event
+ Capability fixture; an integration-tier variant (deferred) can
exercise the same invariant against PostgresEventStore for the
capability_version pin.
"""

from dataclasses import fields
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from cora.operation.aggregates.procedure import (
    RecipeExpansionRecorded,
    to_payload,
)

_NOW = datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC)
_REQUIRED_DENORM_FIELDS = frozenset(
    {
        "recipe_id",
        "recipe_version",
        "capability_id",
        "capability_version",
    }
)


@pytest.mark.architecture
def test_recipe_expansion_recorded_dataclass_declares_denorm_fields() -> None:
    """The event must keep `recipe_id` + `recipe_version` (replay snapshot pin)
    AND `capability_id` + `capability_version` (audit-by-Capability denorm)."""
    declared = {field.name for field in fields(RecipeExpansionRecorded)}
    missing = _REQUIRED_DENORM_FIELDS - declared
    assert not missing, (
        f"RecipeExpansionRecorded missing denorm fields: {sorted(missing)}. "
        f"Anti-hook 15 of project-recipe-aggregate-design pins these as "
        f"the load-bearing escape hatch for audit-by-Capability read paths."
    )


@pytest.mark.architecture
def test_recipe_expansion_recorded_to_payload_carries_denorm_keys() -> None:
    """to_payload must serialize every denorm field; a refactor that
    silently drops one would break audit-by-Capability filters."""
    recipe_id = uuid4()
    capability_id = uuid4()
    event = RecipeExpansionRecorded(
        procedure_id=uuid4(),
        recipe_id=recipe_id,
        recipe_version="v1",
        capability_id=capability_id,
        capability_version="cap-v3",
        bindings={"angle": 30.0},
        expansion_port_version="v1",
        steps_hash="abc",
        bindings_hash="def",
        step_count=1,
        occurred_at=_NOW,
    )
    payload = to_payload(event)
    for key in _REQUIRED_DENORM_FIELDS:
        assert key in payload, (
            f"to_payload({type(event).__name__}) omits denorm key {key!r}; "
            f"audit-by-Capability read paths would lose the {key} pin."
        )
    assert payload["recipe_id"] == str(recipe_id)
    assert payload["capability_id"] == str(capability_id)
    assert payload["recipe_version"] == "v1"
    assert payload["capability_version"] == "cap-v3"


@pytest.mark.architecture
def test_recipe_expansion_recorded_bindings_serialize_canonically() -> None:
    """Bindings serialize via canonical-JSON sort_keys so the persisted
    payload reproduces `bindings_hash`. Distinct-order dicts must serialize
    identically."""
    proc_id = uuid4()
    rec_id = uuid4()
    cap_id = uuid4()

    def _make(bindings: dict[str, object]) -> RecipeExpansionRecorded:
        return RecipeExpansionRecorded(
            procedure_id=proc_id,
            recipe_id=rec_id,
            recipe_version=None,
            capability_id=cap_id,
            capability_version=None,
            bindings=bindings,
            expansion_port_version="v1",
            steps_hash="h",
            bindings_hash="b",
            step_count=0,
            occurred_at=_NOW,
        )

    event_a = _make({"angle": 30.0, "energy": 10.0})
    event_b = _make({"energy": 10.0, "angle": 30.0})
    assert to_payload(event_a)["bindings"] == to_payload(event_b)["bindings"]

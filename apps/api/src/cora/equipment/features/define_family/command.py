"""The `DefineFamily` command — intent dataclass for this slice.

Carries only what the caller controls (the Family's display name +
the affordance set the device class supports). Server-side concerns
(new aggregate id, wall-clock timestamp, correlation id, per-event
ids) are injected by the handler from infrastructure ports.

Status is implicit at definition (`Defined`) and not part of the
command — see the Family aggregate's `state.py` docstring for the
enum-in-state, str-in-event convention.

`affordances` is REQUIRED at definition time per DLM-A Pattern P
(FHIR R5 minimum-cardinality criterion: required iff necessary to
any understanding of the resource — a Family without affordances has
no operational meaning). Empty `frozenset()` is a valid argument the
caller must supply explicitly; the discipline is "caller acknowledged
the choice." Changes to the affordance set flow through `version_family`
(a new version IS a new declaration), NOT via a separate slice.
"""

from dataclasses import dataclass

from cora.equipment.aggregates.family import Affordance


@dataclass(frozen=True)
class DefineFamily:
    """Define a new device-class Family with the given display name and affordance set."""

    name: str
    affordances: frozenset[Affordance]

"""The `SupersedeCaution` command -- intent dataclass for this slice.

Supersedes an Active parent caution by creating a new child caution
with the supplied fields, atomically with the parent's transition to
`Superseded`. The child gets `parent_caution_id=<parent>` on its
genesis event; the parent gets `CautionSuperseded(by_caution_id=
<child>)` on its stream.

The child's fields are operator-supplied (NOT copied from parent) so
supersession can revise any aspect: text, workaround, severity,
category, tags, expires_at, propagate_to_children, author. The
parent-child link establishes the supersession chain.

EXCEPT: the child's `target` MUST equal the parent's `target` (the
decider enforces this via `InvalidCautionSupersedeTargetError`).
Retargeting via supersede confuses lineage; the read-side projection's
'active cautions on Asset X' query needs target-stability across
supersession chains. Operators wanting a different target start a new
caution.

The superseding actor's identity lives on the event envelope
(`StoredEvent.principal_id`); no actor field on the command/event for
the supersede event (the child genesis's `author_actor_id` IS on the
command/event for denorm convenience).
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from cora.caution.aggregates.caution import (
    CautionCategory,
    CautionSeverity,
    CautionTarget,
)


@dataclass(frozen=True)
class SupersedeCaution:
    """Supersede an Active caution with a new child (`parent: Active -> Superseded`).

    Fields mirror `RegisterCaution` (the child IS a registration) +
    `parent_caution_id`. `target` MUST match parent's; the decider
    enforces this.
    """

    parent_caution_id: UUID
    target: CautionTarget
    category: CautionCategory
    severity: CautionSeverity
    text: str
    workaround: str
    author_actor_id: UUID
    tags: frozenset[str] = field(default_factory=frozenset[str])
    expires_at: datetime | None = None
    propagate_to_children: bool = False

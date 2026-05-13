"""Cross-aggregate context the `mount_subject` decider validates against.

`MountSubjectContext` is built by the `mount_subject` handler from a
`load_asset` call before reaching the pure decider. The decider
treats the loaded Asset as opaque domain data and validates the
mount preconditions without performing any I/O.

Mirrors `RunStartContext` (start_run, the canonical 2-instance
example of this pattern in CONTRIBUTING.md). The context dataclass
is slice-local: only `mount_subject` uses it today.

## Field semantics

  - `asset`: the sample-environment Asset being mounted onto.
    Decider rejects if not in `Active` lifecycle (raises
    `SubjectMountTargetUnavailableError`). Existence is checked at
    handler-load time (`AssetNotFoundError` -> 404 from Equipment's
    routes).
"""

from dataclasses import dataclass

from cora.equipment.aggregates.asset import Asset


@dataclass(frozen=True)
class MountSubjectContext:
    """Snapshot of the mount-target Asset at command time."""

    asset: Asset

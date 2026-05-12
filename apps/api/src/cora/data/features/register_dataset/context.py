"""Cross-aggregate context the `register_dataset` decider validates against.

`DatasetRegistrationContext` is built by the `register_dataset`
handler from `load_run` + `load_subject` + per-derived_from
`load_dataset` calls before reaching the pure decider. Per gate-
review Q2 lock B, validation is existence-only (no status check):
the producing Run can be in any state (Datasets register mid-Run
for in-situ measurements), the linked Subject can be in any
lifecycle state, and each derived_from Dataset just needs to exist.

Slice-local module by design: only `register_dataset` uses it
today. Mirrors the `RunStartContext` precedent from 6f-1, the
canonical pattern for cross-aggregate validation in CORA
(documented in CONTRIBUTING.md).

## Field semantics

  - `producing_run`: the Run that produced this Dataset. None
    when the command's `producing_run_id` is None (standalone
    upload, externally-sourced data).
  - `subject`: the Subject the Dataset is about. None when the
    command's `subject_id` is None (calibration / dark-field /
    synthetic data).
  - `derived_from`: dict keyed by dataset_id, loaded from the
    command's `derived_from` set. Empty dict when the command's
    `derived_from` set is empty (raw/captured data).

The decider treats these as opaque proof-of-existence; it never
inspects the loaded entities' state. If any reference fails to
load, the handler raises the appropriate not-found error before
the context is built (so the decider can assume every entry is
valid).
"""

from dataclasses import dataclass, field
from uuid import UUID

from cora.data.aggregates.dataset import Dataset
from cora.run.aggregates.run import Run
from cora.subject.aggregates.subject import Subject


@dataclass(frozen=True)
class DatasetRegistrationContext:
    """Snapshot of cross-aggregate references at Dataset-registration time.

    All three fields are optional / possibly-empty; the handler
    populates each only when the corresponding command field is set.
    The decider uses this purely as proof of existence (never
    inspects state).
    """

    producing_run: Run | None = None
    subject: Subject | None = None
    derived_from: dict[UUID, Dataset] = field(default_factory=dict[UUID, Dataset])

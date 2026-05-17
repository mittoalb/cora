# Cautions

*Caution BC Cautions targeting facility-level Assets. A Caution carries operator tribal knowledge (category, severity, text, workaround) on a target Asset or Procedure. See [Model](../../architecture/model.md) for the aggregate shape.*

*See [Scenarios](../../scenarios/index.md) for the operator routines that exercise this surface.*

| Caution | Target | Category | Severity | Summary |
| --- | --- | --- | --- | --- |
| Top-up flux transients | APS Site Asset | `OperationalWindow` | `Notice` | Top-up injections cause brief beam-flux transients (~0.5s) every few minutes |

Source of truth: [`apps/api/tests/integration/scenarios/test_aps_facility.py`](../../../apps/api/tests/integration/scenarios/test_aps_facility.py).

## Pending in code

Other facility-wide Cautions (storage-ring scheduled downtimes, shared equipment quirks, calibration drift on shared optics) are not yet registered. Each lands as a row above when a scenario test or seed script registers it.

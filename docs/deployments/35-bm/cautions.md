# Cautions

*Caution BC Cautions targeting 35-BM Assets and Procedures. Operator tribal knowledge captured at shakedown / first-light / production time, surfaced on every future Run start via the `CautionLookup` snapshot. See [Model](../../architecture/model.md) for the aggregate shape.*

| Caution | Target | Category | Severity | Summary |
| --- | --- | --- | --- | --- |
| Aerotech cold-start index miss | `Aerotech_ABRS_rotary` (Device) | `Wear` | `Caution` | Misses index pulse on cold-start home; retry once after 5s settling |

Source of truth: [`apps/api/tests/integration/test_35bm_shakedown_motor_homing_scenario.py`](../../../apps/api/tests/integration/test_35bm_shakedown_motor_homing_scenario.py).

## Aerotech cold-start index miss

`Wear` / `Caution`. Tags: `aerotech`, `home`, `cold_start`.

**Observation.** The Aerotech ABRS rotary stage misses its index pulse on the first home attempt after a power cycle. Subsequent homes work; only the cold-start first attempt is affected. Observed during 35-BM shakedown on 2026-05-17.

**Workaround.** Issue `HOME` command, wait 5s for settling, re-issue `HOME`. Verify `index_pulse=1` on encoder readback before treating home as successful. Optionally pre-warm the stage by jogging +/-1° before the first home.

**Lifetime.** No `expires_at` (permanent until superseded or retired). Persists on the operator banner for every future Run start at 35-BM until the underlying stage is replaced or recalibrated.

## Pending in code

Other 35-BM Cautions (detector dark-frame drift after long beam-off periods, scintillator browning under prolonged white-beam exposure, sample-stage backlash after manual handling) are not yet registered. Each lands as a row above when a scenario test registers it.

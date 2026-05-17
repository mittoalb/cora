# Cautions

*Caution BC Cautions targeting 2-BM Assets and Procedures. Operator tribal knowledge captured at shakedown / first-light / production time, surfaced on every future Run start via the `CautionLookup` snapshot. See [Model](../../architecture/model.md) for the aggregate shape.*

| Caution | Target | Category | Severity | Summary |
| --- | --- | --- | --- | --- |
| Aerotech cold-start index miss | `Aerotech_ABRS_rotary` (Device) | `Wear` | `Caution` | Misses index pulse on cold-start home; retry once after 5s settling |

Source of truth: [`apps/api/tests/integration/scenarios/test_2bm_motor_homing.py`](../../../apps/api/tests/integration/scenarios/test_2bm_motor_homing.py).

## Aerotech cold-start index miss

`Wear` / `Caution`. Tags: `aerotech`, `home`, `cold_start`.

**Observation.** The Aerotech ABRS rotary stage misses its index pulse on the first home attempt after a power cycle. Subsequent homes work; only the cold-start first attempt is affected. Observed during 2-BM shakedown on 2026-05-17.

**Workaround.** Issue `HOME` command, wait 5s for settling, re-issue `HOME`. Verify `index_pulse=1` on encoder readback before treating home as successful. Optionally pre-warm the stage by jogging +/-1° before the first home.

**Lifetime.** No `expires_at` (permanent until superseded or retired). Persists on the operator banner for every future Run start at 2-BM until the underlying stage is replaced or recalibrated.

## Pending in code

Other 2-BM Cautions surfaced by the [2-BM repo survey](https://github.com/xray-imaging/2bm-docs) or open watch items. Each lands as a row above when a scenario test (or seed script) registers it.

| Pending Caution | Target | Source scenario (planned) |
| --- | --- | --- |
| Hexapod cold-start controller lockup | Hexapod Device | `tests/integration/scenarios/test_2bm_hexapod_reboot.py` (sourced from `2bmb-bin/hexapod_reboot.py`: PDU outlet 4 power-cycle + IOC restart) |
| Vibration threshold exceeded after air-handler shutdown | 2-BM Unit | `tests/integration/scenarios/test_2bm_vibration_baseline.py` (registers the Caution only when measured vibration frequency exceeds reference) |
| Detector dark-frame drift after long beam-off periods | `Oryx_5MP_camera` Device | Not yet sourced; would land when an operations-phase scenario observes the drift |
| Scintillator browning under prolonged white-beam exposure | `Scintillator_LuAG` Device | Not yet sourced; needs long-duration operations scenario |
| Sample-stage backlash after manual handling | Sample-stage Devices | Not yet sourced; needs manual-intervention recovery scenario |

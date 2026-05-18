# Cautions

*Caution BC Cautions targeting 2-BM Assets and Procedures.*

Operator tribal knowledge captured at shakedown, first-light, or production time. Surfaced on every future Run start via the `CautionLookup` snapshot. See [Model](../../architecture/model.md) for the aggregate shape.

| Target | Category | Severity | Text |
| --- | --- | --- | --- |
| `Aerotech_ABRS_rotary` | `Wear` | `Caution` | Misses index pulse on cold-start home; retry after 5s |
| `Hexapod_2BM` | `Wear` | `Caution` | Locks up under sustained load; recover via `hexapod_reboot` |

## Aerotech cold-start index miss

`Wear` / `Caution`. Tags: `aerotech`, `home`, `cold_start`.

**Observation.** The Aerotech ABRS rotary stage misses its index pulse on the first home attempt after a power cycle. Subsequent homes work; only the cold-start first attempt is affected. Observed during 2-BM shakedown on 2026-05-17.

**Workaround.** Issue `HOME` command, wait 5s for settling, re-issue `HOME`. Verify `index_pulse=1` on encoder readback before treating home as successful. Optionally pre-warm the stage by jogging +/-1° before the first home.

**Lifetime.** No `expires_at` (permanent until superseded or retired). Persists on the operator banner for every future Run start at 2-BM until the underlying stage is replaced or recalibrated.

## Hexapod controller lockup

`Wear` / `Caution`. Tags: `hexapod`, `controller_lockup`, `pdu_power_cycle`, `ioc_restart`.

**Observation.** The PI-Hexapod sample-positioning controller occasionally locks up under sustained load: the `2bmHXP:HexapodAllEnabled` EPICS PV reads `0` while motion commands return no error. Operator-observable symptom is the hexapod stops responding to position requests even though no fault has been raised by the motion-control layer.

**Workaround.** Run `hexapod_reboot.py` (in [`2bmb-bin`](https://github.com/xray-imaging/2bmb-bin)): stops the hexapod IOC, power-cycles PDU outlet 4 with 10s settling each way, restarts the IOC, polls `HexapodAllEnabled` for up to 180s. If the PV is still `0` after the timeout, `caput 2bmHXP:EnableWork.PROC 1` to force-enable, then re-poll. Manual checks during recovery: verify outlet state via NetBooter `/status.xml`; SSH `2bmb@arcturus` for IOC log inspection.

**Lifetime.** No `expires_at` (permanent until superseded or retired). Surfaces on every future Run start at 2-BM that targets the Hexapod, so operators know to run the recovery routine on first sign of unresponsiveness rather than chasing a phantom motion-control bug.

## Pending

| Target | Category | Severity | Text |
| --- | --- | --- | --- |
| 2-BM Unit | | | Vibration threshold exceeded after air-handler shutdown |
| `Oryx_5MP_camera` | | | Detector dark-frame drift after long beam-off periods |
| `Scintillator_LuAG` | | | Scintillator browning under prolonged white-beam exposure |
| Sample-stage Devices | | | Sample-stage backlash after manual handling |

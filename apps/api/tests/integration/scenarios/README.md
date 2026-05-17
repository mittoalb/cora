# Scenarios

Each test in this folder exercises one operator routine end-to-end through CORA's BC stack. The pattern is **Living Documentation** (Gojko Adzic, *Specification by Example*, 2011; Cyrille Martraire, *Living Documentation*, 2019): scenario tests are both machine-runnable verification AND the source of truth for per-beamline doc pages under `docs/deployments/`.

A doc page may only name an aggregate that some scenario here has registered. That makes scenario coverage the bottleneck on doc completeness.

## Filename

`test_<beamline-or-facility>_<routine>.py`

Where:

- `<beamline-or-facility>` is `argonne`, `aps`, `35bm`, `7bm`, `maxiv`, ... (lowercase, no dashes). It maps directly to `docs/deployments/<beamline-or-facility>/`.
- `<routine>` is the operator routine in snake_case (`motor_homing`, `alignment_center`, `dark_baseline`, `first_light`, `facility`).

The `scenarios/` folder is the marker; no `_scenario.py` suffix.

## Rules

1. **One scenario = one routine.** No compendium scenarios that test multiple routines back-to-back. If two routines must run together (state dependency), they are still two scenarios; the second consumes a fixture that runs the first.

2. **Filename matches doc folder.** `test_aps_*` populates `docs/deployments/aps/`; `test_2bm_*` populates `docs/deployments/2-bm/`. Cross-facility vocabulary the scenario registers (Methods, Capabilities) also lands in `docs/catalog/`.

3. **Multi-maturity discriminator (deferred).** If a single routine ever needs scenarios at two different maturities (for example, an unattended-operations variant of an alignment routine), add a suffix at *that* point: `test_<beamline>_<routine>_<suffix>.py`. Until then, single scenario per routine.

## Template

Copy from a recent sibling. [`test_2bm_dark_baseline.py`](test_2bm_dark_baseline.py) and [`test_2bm_alignment_resolution.py`](test_2bm_alignment_resolution.py) are good starting points; both consume [`_facility_fixture.py`](_facility_fixture.py) for the standard install ceremony.

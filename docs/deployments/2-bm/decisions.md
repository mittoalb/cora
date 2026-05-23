# Decisions

*Decision BC Decisions emitted at 2-BM.*

A Decision is a structured-audit record of a consequential choice, attributed to a human or agent Actor. See [Model](../../architecture/model.md) for the aggregate shape.

| Actor | Context | Choice |
| --- | --- | --- |
| `Run Debrief` agent | `RunDebriefer` | `NominalCompletion` |
| `Run Debrief` agent | `RunDebriefer` | `DegradedCompletion` |
| `Run Debrief` agent | `RunDebriefer` | `EquipmentAbort` |
| 2-BM Operator | `EnergyChange` | `switch_to_30_keV` |

## Pending

| Actor | Context | Choice |
| --- | --- | --- |
| `Run Debrief` agent | `RunDebriefer` | `OperatorAbort` |
| `Run Debrief` agent | `RunDebriefer` | `DataSuspect` |
| Strategy agent (8g) | | |

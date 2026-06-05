# Decisions

*Decision BC Decisions emitted at 2-BM.*

A Decision is a structured-audit record of a consequential choice, attributed to a human or agent Actor. See [Model](../../architecture/model.md) for the aggregate shape.

| Actor | Context | Choice |
| --- | --- | --- |
| `RunDebriefer` agent | `RunDebrief` | `NominalCompletion` |
| `RunDebriefer` agent | `RunDebrief` | `DegradedCompletion` |
| `RunDebriefer` agent | `RunDebrief` | `EquipmentAbort` |
| 2-BM Operator | `EnergyChange` | `switch_to_30_keV` |

## Pending

| Actor | Context | Choice |
| --- | --- | --- |
| `RunDebriefer` agent | `RunDebrief` | `OperatorAbort` |
| `RunDebriefer` agent | `RunDebrief` | `DataSuspect` |
| Strategy agent (8g) | | |

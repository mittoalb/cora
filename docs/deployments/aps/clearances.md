# Clearances

*Safety BC Clearances issued at APS.*

Each Clearance carries a `kind` (one of 10 facility forms: ESAF, SAF, AForm, DUO, ESRA, ERA, PLHD, DOOR, BTR, Form9) and binds to one or more CORA aggregates or external references. See [Model](../../architecture/model.md) for the aggregate shape.

| Clearance | Kind | Bindings |
| --- | --- | --- |
| `Facility umbrella` | `ESAF` | APS Site Asset |

## Pending

| Clearance | Kind | Bindings |
| --- | --- | --- |
| Per-experiment ESAFs | `ESAF` | per-proposal Subject + Run |
| Synchrotron access | `SAF` | |
| Door interlocks | `DOOR` | |

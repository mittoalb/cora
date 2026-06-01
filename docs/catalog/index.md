# Catalog

*Cross-facility vocabulary. Three inventories aggregate at this level: [Capabilities](capabilities.md) (the operations-layer template namespace, governed cross-facility), [Methods](methods.md) (the technique catalog, each bound to one Capability), and [Families](families.md) (the device-class abstractions Methods declare as `needed_family_ids`). All three are shared across APS, MAX IV, and any future site CORA serves.*

## Inventories

- [Capabilities](capabilities.md): Recipe BC operations-layer templates (`cora.capability.*`) — the closed-core vocabulary for what an operation provides
- [Methods](methods.md): Recipe BC technique catalog (ISA-88 General Recipe layer) — each Method binds to one Capability
- [Families](families.md): Equipment BC device-class abstractions — each Method declares `needed_family_ids` against this list

Source of truth: the scenario integration tests.

# Auth

For implementers wiring authentication and authorization. Each row names a role, the current pick (or planned pick), and the trigger that would force a swap.

## Authentication

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Auth wiring | `X-Principal-Id` behind a verifying proxy | App-side contract; deployment-side proxy is where it lands | Application-side contract stays; proxy is where deployments swap |

## Authorization

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Authz model (planned) | ReBAC (SpiceDB or OpenFGA) | Multi-stakeholder ownership in shared facilities | Locked when first non-Cedar authz rule lands |
| Decision-BC policy language | Cedar | Used in Decision predicates (`has_determining_policies`) | Stays |

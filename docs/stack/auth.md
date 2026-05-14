# Auth

*Authentication wiring, authorization model, policy language.*

| Role | Pick | Why | Swap trigger |
| --- | --- | --- | --- |
| Auth wiring | `X-Principal-Id` behind a verifying proxy | Dev/test fallback; production fronts with a proxy that strips client headers and sets the verified value | Application-side contract stays; proxy is where deployments swap |
| Authz model (planned) | ReBAC (SpiceDB or OpenFGA) | Multi-stakeholder ownership in shared facilities | Locked when first non-Cedar authz rule lands |
| Decision-BC policy language | Cedar | Used in Decision predicates (`has_determining_policies`) | Stays |

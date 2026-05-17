# Deployments

*Pilots earn the abstractions.*

Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it. A deployment is a real-world scope at some level of the Asset hierarchy (an enterprise, a site, or an instrument) where the recipe ladder, BCs, and trust boundaries meet actual users. Until a deployment demands a shape, the shape stays out.

## Active

Deployments mirror CORA's Asset hierarchy (Enterprise → Site → Area → Unit):

| Deployment | Level | Parent | Status |
| --- | --- | --- | --- |
| [Argonne](argonne/index.md) | Enterprise | (root) | Operational |
| [APS](aps/index.md) | Site | Argonne | Operational |
| [2-BM](2-bm/index.md) | Unit | Sector 2 (Area, under APS) | Operational |
| [35-BM](35-bm/index.md) | Unit | Sector 35 (Area, under APS) | Planned |

Cross-facility vocabulary (Capabilities, Methods) lives in the [Catalog](../catalog/index.md), since it is not bound to any single Site.

Each page name names its role (`assets`, `practices`, `procedures`, ...). A page exists only when there is code-grounded content to fill it. Stakeholder-facing framing (pilot vision, scope, why-this-beamline) lives in the [slide deck](../talks.md) instead.

Most inventory pages place by Asset hierarchy (Methods at Site, Procedures at beamline, and so on). The two scope-free identity aggregates (Access BC `Actor`, Agent BC `Agent`) instead place by *registrar-ceremony scope*: the deployment folder whose canonical install fixture contains the `register_actor` or `define_agent` call. That is why APS has `actors.md` plus `agents.md` (facility-wide principals) while 2-BM has `actors.md` (beamline-bound principals), with no `scope` field on the aggregate itself.

The Trust BC (zones, conduits, policies) intentionally has no deployment-page surface: it is system plumbing for cross-BC identity and access, not a per-deployment inventory operators would browse.

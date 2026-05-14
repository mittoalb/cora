# Projects

*Pilots earn the abstractions.*

Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it. A project is a real instrument with real users where the recipe ladder, BCs, and trust boundaries get stress-tested. Until a project takes a shape on, the shape stays out.

## Active

| Project | Status | Where |
| --- | --- | --- |
| [35-BM](35-bm/index.md) | In design | APS, Argonne |

## Template

Every project under `docs/projects/<id>/` follows the same five-page template. Each page does one job. Thin content in any section signals the deployment is not ready.

| Page | Role |
| --- | --- |
| `index` | The whole story in one read: framing, workflow, why this beamline first |
| `ground` | What the pilot inherits at this beamline: assets, software, trust topology, BC↔domain bridge |
| `scope` | What the pilot commits to and what it does not, with the measurable form of "it works" per commit. AI and autonomy as a first-class subsection (in scope, not in scope, stress) |
| `walk` | One experiment walked end to end, the canonical example for this beamline |
| `capabilities` | What the pilot leaves the beamline capable of after delivery |

The template is audience-neutral: each page name names the role, not the modality or facility. The same shape works for micro-CT, sprays, nano-imaging, or anything else a beamline pilot covers.

## Adding a project

1. Copy `docs/projects/35-bm/` to `docs/projects/<new-id>/`
2. Update each page
3. Add the project to `mkdocs.yml` under Projects
4. Add a row to the Active table above

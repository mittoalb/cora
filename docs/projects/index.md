# Projects

*Pilots earn the abstractions.*

Vertical before horizontal. CORA's domain model only contains what at least one real deployment forced into it. A project is a real instrument with real users where the recipe ladder, BCs, and trust boundaries get stress-tested. Until a project takes a shape on, the shape stays out.

## Active

| Project | Status | Where |
| --- | --- | --- |
| [35-BM](35-bm/index.md) | In design | APS, Argonne |

## Template

Every project under `docs/projects/<id>/` follows the same eight-page template. Thin content in any section signals the deployment is not ready.

| Page | Contents |
| --- | --- |
| Overview | What the project is and why now |
| Goals | Commitments, non-commitments, success criteria |
| Substrate | Asset hierarchy, software ecosystem, trust topology |
| Approach | BCs, recipe ladder, governance shape |
| Samples | Sample classes the project targets |
| Experiment | One worked example, end to end |
| Features | Stress-tested features with success criteria |
| Horizon | What comes after the project completes |

## Adding a project

1. Copy `docs/projects/35-bm/` to `docs/projects/<new-id>/`
2. Update each page
3. Add the project to `mkdocs.yml` under Projects
4. Add a row to the Active table above

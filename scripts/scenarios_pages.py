"""Render scenario taxonomy pages from parsed metadata.

Each function returns markdown text. The mkdocs hook in
scripts/mkdocs_hooks.py wraps them as virtual `File` instances under
docs/scenarios/. Closed vocabularies and parser live in
scripts/scenarios_meta.py.

Page set:
  - index.md             — scenarios overview (cluster summary table)
  - <cluster>.md (x 5)   — one per closed cluster value, table-only
                           (Step 4 will add hand-authored intro prose
                           via a separate intros directory)
  - by-archetype.md      — pivot by archetype with H2 per value
  - by-bc.md             — registry of all 14 BCs with coverage counts
  - tests/<stem>.md      — one stub per scenario with tags + GitHub link
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from scenarios_meta import ARCHETYPES, BOUNDED_CONTEXTS, CLUSTERS, ScenarioMeta

GITHUB_BLOB = "https://github.com/xmap/cora/blob/main/"
SCENARIOS_TEST_PATH = "apps/api/tests/integration/scenarios"
INTROS_DIR = Path(__file__).resolve().parent / "scenarios_intros"

# Cluster ordering for stable rendering (matches reading-order convention
# from README and project_scenario_taxonomy memory).
CLUSTER_ORDER: tuple[str, ...] = (
    "Seed",
    "Commissioning",
    "Staging",
    "Runs",
    "Advisories",
)

ARCHETYPE_ORDER: tuple[str, ...] = (
    "setup-only",
    "single-routine",
    "full-run-lifecycle",
    "fsm-walk",
    "gate-enforcement",
    "agent-driven",
)


def _stem_to_label(stem: str) -> str:
    # `test_2bm_tomography_scan` -> `tomography_scan`
    parts = stem.split("_", 2)
    return parts[2] if len(parts) >= 3 and parts[0] == "test" else stem


def _scenario_link(stem: str) -> str:
    return f"tests/{stem}.md"


def _github_link(stem: str) -> str:
    return f"{GITHUB_BLOB}{SCENARIOS_TEST_PATH}/{stem}.py"


def _cluster_row(meta: ScenarioMeta) -> str:
    """Cluster-table row: 2 columns, shape as inline code after the link.

    BCs deliberately omitted: cluster pages are dominated by repeated BC
    info (every Run scenario has Run as primary). BC detail lives on the
    per-scenario stub and on the by-bc registry.
    """
    label = _stem_to_label(meta.stem)
    return (
        f"| [{label}]({_scenario_link(meta.stem)}) `{meta.archetype}` "
        f"| {meta.gist} |"
    )


def render_index(metas: list[ScenarioMeta]) -> str:
    cluster_counts = Counter(m.cluster for m in metas)
    lines: list[str] = ["# Scenarios", ""]
    lines.append(
        "The operator routines CORA exercises end-to-end through its BC stack. "
        "Each test here is also the source of truth for its corresponding entries "
        "on the [Deployments](../deployments/index.md) inventory pages."
    )
    lines.append("")
    lines.append("## Browse by purpose")
    lines.append("")
    lines.append("| Cluster | Today | What's in it |")
    lines.append("| --- | ---: | --- |")
    cluster_blurbs = {
        "Seed": "Facility install + Agent BC config + Supply state",
        "Commissioning": "Alignment chain + non-alignment bring-up + detector baselines",
        "Staging": "Pre-Run intake + clearance gates",
        "Runs": "Acquisition variants + lifecycle edges",
        "Advisories": "Agent-driven subscriber output",
    }
    for cluster in CLUSTER_ORDER:
        count = cluster_counts.get(cluster, 0)
        lines.append(
            f"| [{cluster}]({cluster.lower()}.md) | {count} | {cluster_blurbs[cluster]} |"
        )
    lines.append("")
    lines.append("## Browse by other axes")
    lines.append("")
    lines.append(
        "- [By shape](by-archetype.md): setup-only, single-routine, "
        "full-run-lifecycle, FSM walk, gate enforcement, agent-driven"
    )
    lines.append(
        "- [By bounded context](by-bc.md): which BCs are heavily exercised "
        "and which still have gaps"
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def _load_intro(cluster: str) -> str | None:
    """Hand-authored intro prose for a cluster, if present."""
    path = INTROS_DIR / f"{cluster.lower()}.md"
    if not path.exists():
        return None
    return path.read_text().strip()


def render_cluster(cluster: str, metas: list[ScenarioMeta]) -> str:
    members = sorted(
        (m for m in metas if m.cluster == cluster), key=lambda m: m.stem
    )
    lines: list[str] = [f"# {cluster}", ""]
    intro = _load_intro(cluster)
    if intro:
        lines.append(intro)
        lines.append("")
        lines.append(
            "For domain instances these scenarios produce (Runs, Subjects, "
            "Assets), see the per-beamline "
            "[Deployments](../deployments/index.md) inventories."
        )
    else:
        lines.append(
            f"*Auto-generated table of scenarios in the **{cluster}** cluster.* "
            f"For Run instances and other domain state these scenarios produce, "
            f"see the per-beamline [Deployments](../deployments/index.md) inventories."
        )
    lines.append("")
    if not members:
        lines.append("_No scenarios in this cluster yet._")
        lines.append("")
        return "\n".join(lines) + "\n"
    lines.append("## Scenarios")
    lines.append("")
    lines.append("| Scenario | Gist |")
    lines.append("| --- | --- |")
    for meta in members:
        lines.append(_cluster_row(meta))
    lines.append("")
    return "\n".join(lines) + "\n"


def render_by_archetype(metas: list[ScenarioMeta]) -> str:
    by_arch: dict[str, list[ScenarioMeta]] = defaultdict(list)
    for m in metas:
        by_arch[m.archetype].append(m)
    lines: list[str] = ["# Scenarios by shape", ""]
    lines.append(
        "Pivot of the corpus by archetype (how each test is constructed). "
        "Same scenarios are grouped by purpose under [Clusters](index.md#browse-by-purpose) "
        "and by BC under [by-bc](by-bc.md)."
    )
    lines.append("")
    for archetype in ARCHETYPE_ORDER:
        members = sorted(by_arch.get(archetype, []), key=lambda m: m.stem)
        # Explicit anchor (attr_list) so per-scenario stubs can link to
        # the archetype section without the count breaking the slug.
        lines.append(f"## `{archetype}` ({len(members)}) {{ #{archetype} }}")
        lines.append("")
        if not members:
            lines.append("_No scenarios with this shape yet._")
            lines.append("")
            continue
        lines.append("| Scenario | Cluster | Gist |")
        lines.append("| --- | --- | --- |")
        for meta in members:
            label = _stem_to_label(meta.stem)
            lines.append(
                f"| [{label}]({_scenario_link(meta.stem)}) | "
                f"[{meta.cluster}]({meta.cluster.lower()}.md) | {meta.gist} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_by_bc(metas: list[ScenarioMeta]) -> str:
    primary_counts = Counter(m.bc_primary for m in metas)
    touches_counts: Counter[str] = Counter()
    for m in metas:
        for bc in m.bc_touches:
            touches_counts[bc] += 1
    lines: list[str] = ["# Scenarios by bounded context", ""]
    lines.append(
        "All 14 BCs in CORA's codebase, with scenario coverage today. "
        "BCs with zero `bc_primary` scenarios remain visible as coverage "
        "gaps (OpenTelemetry registry pattern)."
    )
    lines.append("")
    lines.append("| BC | Primary in | Touched in |")
    lines.append("| --- | ---: | ---: |")
    for bc in sorted(BOUNDED_CONTEXTS):
        lines.append(f"| {bc} | {primary_counts.get(bc, 0)} | {touches_counts.get(bc, 0)} |")
    lines.append("")
    lines.append("## Per-BC scenarios")
    lines.append("")
    lines.append(
        "*In each table below, **bold** scenario names mean that BC is the "
        "scenario's primary; plain names mean the BC is touched but not primary.*"
    )
    lines.append("")
    for bc in sorted(BOUNDED_CONTEXTS):
        members = sorted(
            (m for m in metas if bc in m.bc_touches), key=lambda m: m.stem
        )
        # Explicit anchor (attr_list) so per-scenario stubs can link to
        # the BC section without the count breaking the slug.
        lines.append(f"### {bc} ({len(members)}) {{ #{bc.lower()} }}")
        lines.append("")
        if not members:
            lines.append("_No scenarios touch this BC yet._")
            lines.append("")
            continue
        # 3-column table: bold scenario name flags primary-BC role.
        lines.append("| Scenario | Cluster | Gist |")
        lines.append("| --- | --- | --- |")
        for meta in members:
            label = _stem_to_label(meta.stem)
            link = f"[{label}]({_scenario_link(meta.stem)})"
            scenario_cell = f"**{link}**" if meta.bc_primary == bc else link
            lines.append(
                f"| {scenario_cell} "
                f"| [{meta.cluster}]({meta.cluster.lower()}.md) "
                f"| {meta.gist} |"
            )
        lines.append("")
    return "\n".join(lines) + "\n"


def render_scenario_stub(meta: ScenarioMeta) -> str:
    label = _stem_to_label(meta.stem)
    touches = [t for t in meta.bc_touches if t != meta.bc_primary]
    lines: list[str] = [f"# {label}", ""]
    lines.append(f"> {meta.gist}")
    lines.append("")
    lines.append(
        f"**Cluster** [{meta.cluster}](../{meta.cluster.lower()}.md) "
        f"· **Shape** [`{meta.archetype}`](../by-archetype.md#{meta.archetype}) "
        f"· **Primary BC** [{meta.bc_primary}](../by-bc.md#{meta.bc_primary.lower()})"
    )
    if touches:
        touch_links = ", ".join(
            f"[{bc}](../by-bc.md#{bc.lower()})" for bc in touches
        )
        lines.append("")
        lines.append(f"**Also touches** {touch_links}")
    lines.append("")
    lines.append(f"[View source on GitHub →]({_github_link(meta.stem)})")
    lines.append("")
    return "\n".join(lines) + "\n"


def render_all(metas: list[ScenarioMeta]) -> dict[str, str]:
    """Return src_uri -> markdown for every page in the scenarios surface."""
    pages: dict[str, str] = {
        "scenarios/index.md": render_index(metas),
        "scenarios/by-archetype.md": render_by_archetype(metas),
        "scenarios/by-bc.md": render_by_bc(metas),
    }
    for cluster in CLUSTERS:
        pages[f"scenarios/{cluster.lower()}.md"] = render_cluster(cluster, metas)
    for meta in metas:
        pages[f"scenarios/tests/{meta.stem}.md"] = render_scenario_stub(meta)
    return pages


__all__ = [
    "ARCHETYPE_ORDER",
    "CLUSTER_ORDER",
    "render_all",
    "render_by_archetype",
    "render_by_bc",
    "render_cluster",
    "render_index",
    "render_scenario_stub",
]

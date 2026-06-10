"""Pin the AssetLevel upper-tier deprecation (Slice 8B).

Per [[project-slice8-design]] L4, the upper three `AssetLevel`
values (`ENTERPRISE` / `SITE` / `AREA`) are DEPRECATED in favor of
`Asset.facility_code` (Slice 8A binding to Federation Facility,
shipped 2026-06-09). The lower three values
(`UNIT` / `COMPONENT` / `DEVICE`) graduate to a separate closed
`AssetTier` StrEnum (Slice 8B, shipped 2026-06-10) that carries an
honest intrinsic-tier meaning without the facility-envelope
ambiguity.

## What this fitness enforces

Symbolic references to `AssetLevel.ENTERPRISE` / `AssetLevel.SITE` /
`AssetLevel.AREA` are REJECTED under the production source tree
(`apps/api/src/cora/`), with a narrow allow-list for the three
legitimate carriers: the enum definition site, the register_asset
decider's parent-id-null invariant arm, and the relocate_asset
decider's parent-id-null invariant arm.

## What this fitness deliberately does NOT enforce

  - String literal scan: deliberately omitted per Lock L4
    rationale. `"Enterprise"` / `"Site"` / `"Area"` are common
    tokens that collide with `FacilityKind.SITE = "Site"` /
    `FacilityKind.AREA = "Area"` (locked in
    [[project-facility-aggregate-design]]) and with ISA-95 prose.
    A string-literal sweep would force an allowlist swelling to
    dozens of legitimate Federation, Supply, and standards-text
    sites, defeating the purpose. The symbolic check is the right
    guard.
  - Test-tree scan: tests legitimately exercise the existing
    upper-tier behavior; the deprecation is about NEW production-
    tier usage. Test-tier fixtures like
    `tests/integration/scenarios/_facility_fixture.py` install
    canonical APS Site / Area Assets and stay valid until the
    post-pilot enum-member drop migration.
  - Runtime behavior: existing AssetLevel upper-tier values still
    register, evolve, and surface in projections normally. The
    deprecation signal is fitness-only; the post-pilot forward-
    only migration drops the members at the enum level.

## Allow-list discipline

Three entries today:
  - The enum definition (`Asset` state.py)
  - register_asset decider's parent-id-null invariant arm
  - relocate_asset decider's parent-id-null invariant arm

Widen ONLY at gate review and only with a one-line rationale.
The arch-fitness self-test confirms every allow-listed file
actually contains the deprecated symbol (so dead entries cannot
accumulate).
"""

from pathlib import Path

import pytest

from tests.architecture.conftest import tracked_python_files

_DEPRECATED_SYMBOLS: tuple[str, ...] = (
    "AssetLevel.ENTERPRISE",
    "AssetLevel.SITE",
    "AssetLevel.AREA",
)

# Production source tree under inspection. The deprecation signal
# applies to NEW code under cora/equipment/, cora/run/, and
# cora/operation/; tests stay free to exercise the existing
# behavior until the post-pilot migration drops the enum members.
_SCAN_SUBTREES: tuple[str, ...] = (
    "apps/api/src/cora/equipment/",
    "apps/api/src/cora/run/",
    "apps/api/src/cora/operation/",
)

# Files allowed to carry the symbolic references. Each entry maps
# to a structural reason; widen at gate review only.
_ALLOW_RELATIVE_PATHS: frozenset[str] = frozenset(
    {
        # The enum definition itself names every value, including
        # the deprecated upper tiers. Always allow-listed.
        "apps/api/src/cora/equipment/aggregates/asset/state.py",
        # The register_asset decider enforces the parent-id-null
        # invariant on the Enterprise level (and the converse on
        # other levels). The symbolic reference IS the load-bearing
        # invariant check; cannot be removed during the deprecation
        # window.
        "apps/api/src/cora/equipment/features/register_asset/decider.py",
        # The relocate_asset decider applies the same parent-id-null
        # invariant to the relocate event. Same load-bearing
        # rationale as register_asset.
        "apps/api/src/cora/equipment/features/relocate_asset/decider.py",
    }
)


def _scan_subtree_for_symbol(
    paths: frozenset[Path],
    needle: str,
    repo_root: Path,
) -> list[tuple[Path, int, str]]:
    """Return every line in `paths` (filtered to the production source
    subtrees) that contains `needle`, excluding allow-listed files."""
    hits: list[tuple[Path, int, str]] = []
    for path in paths:
        try:
            relative = path.relative_to(repo_root).as_posix()
        except ValueError:
            relative = path.as_posix()
        if not any(relative.startswith(prefix) for prefix in _SCAN_SUBTREES):
            continue
        if relative in _ALLOW_RELATIVE_PATHS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            if needle in line:
                hits.append((path, line_no, line.strip()))
    return hits


@pytest.mark.architecture
@pytest.mark.parametrize("symbol", _DEPRECATED_SYMBOLS)
def test_deprecated_asset_level_upper_tier_not_in_production_source(
    symbol: str,
) -> None:
    """Each of `AssetLevel.ENTERPRISE` / `AssetLevel.SITE` /
    `AssetLevel.AREA` MUST NOT appear under `cora/equipment/`,
    `cora/run/`, or `cora/operation/` outside the narrow
    allow-list (the enum definition + the two parent-id-null
    invariant arms).

    The runtime tolerates the upper tiers in existing code (the
    decider continues to enforce the parent-id-null rule); the
    fitness only blocks NEW code from adopting them. Bind to
    `Asset.facility_code` (Slice 8A) for facility-envelope concerns;
    use `AssetTier` (Slice 8B) for the intrinsic operational tier.
    """
    repo_root = Path(__file__).resolve().parents[4]
    hits = _scan_subtree_for_symbol(tracked_python_files(), symbol, repo_root)
    assert hits == [], (
        f"Found {len(hits)} new reference(s) to deprecated {symbol} under "
        f"production source. Bind to Asset.facility_code (Slice 8A) for "
        f"facility-envelope concerns, or use AssetTier (Slice 8B) for the "
        f"intrinsic operational tier. Widen the allow-list at gate review "
        f"if the new site is genuinely load-bearing for the deprecation "
        f"window.\n" + "\n".join(f"  {p}:{n}: {line}" for p, n, line in hits)
    )


@pytest.mark.architecture
def test_allow_list_entries_actually_contain_deprecated_symbols() -> None:
    """Every file on `_ALLOW_RELATIVE_PATHS` must actually contain at
    least one deprecated symbol. Catches dead allow-list entries
    after a refactor moves the load-bearing reference elsewhere."""
    repo_root = Path(__file__).resolve().parents[4]
    stale: list[str] = []
    for relative in sorted(_ALLOW_RELATIVE_PATHS):
        path = repo_root / relative
        if not path.exists():
            stale.append(f"{relative} (file does not exist)")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not any(symbol in text for symbol in _DEPRECATED_SYMBOLS):
            stale.append(f"{relative} (no deprecated symbol present)")
    assert stale == [], (
        f"Found {len(stale)} stale allow-list entries in "
        f"test_asset_level_upper_tier_deprecated.py; remove them:\n"
        + "\n".join(f"  {entry}" for entry in stale)
    )

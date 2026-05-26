"""JSON Schema property keys don't end in unit suffixes.

Per ``docs/reference/conventions.md`` Units of measurement:

  > Do not put units in field names. ``start_position``, not
  > ``start_position_mm``; ``energy``, not ``energy_kev``. The whole
  > point of the annotation is to escape the lock-in that field
  > suffixes create.

The unit travels in the ``unit: {system, code}`` annotation alongside
the field's type/min/max; the property key stays unit-agnostic. A
schema with ``"energy"`` as a key locks every downstream consumer
into ``keV`` forever and silently breaks when a partner facility wants
to publish the same field as ``eV`` or ``MeV``.

This fitness function AST-walks every tracked ``.py`` file under
``src/cora``, finds dict literals containing a ``"properties"`` key,
and rejects any property whose name ends in a recognised unit suffix.
Detection is per-key, not per-file: an allowlist of grandfathered
(file, key) pairs survives the unit-suffix migration without
locking the whole file.
"""

from __future__ import annotations

import ast
import re
from typing import TYPE_CHECKING

import pytest

from tests.architecture.conftest import CORA_ROOT, tracked_python_files

if TYPE_CHECKING:
    from pathlib import Path


# Broad recognised unit suffixes; intentionally over-inclusive so future
# fields can't sneak in a new unit with an unfamiliar suffix. Match is
# case-sensitive on suffix to allow `_s` (seconds) but not `_S` (siemens).
_UNIT_SUFFIX = re.compile(
    r"_("
    r"eV|keV|MeV|GeV|"  # energy (beam physics)
    r"nm|um|µm|mm|cm|m|km|"  # length
    r"ns|us|µs|ms|sec|seconds|s|min|h|hr|"  # time
    r"Hz|kHz|MHz|GHz|"  # frequency
    r"px|pixel|pixels|"  # imaging
    r"ug|mg|g|kg|"  # mass
    r"A|mA|uA|"  # current
    r"V|mV|kV|"  # voltage
    r"K|degC|degF|"  # temperature
    r"Pa|kPa|MPa|bar|psi|torr|mbar|"  # pressure
    r"rad|mrad|deg|degrees|arcsec|arcmin|"  # angle
    r"counts|cps|"  # counts
    r"kev"  # legacy lowercase (specifically the audit's B3 hit)
    r")$"
)


# Entries are "<qualified-module>:property_key". Each cites the audit
# finding; the matching entry is removed when the property is renamed.
# B3 (rotation_center + detector_pixel_size keys with unit suffixes)
# was the only entry; cleared when the schemas were rewritten without
# the suffixes. The frozenset stays as the documented escape hatch
# for future renames that need a transition window.
GRANDFATHERED_PROPERTY_KEYS: frozenset[str] = frozenset()


def _qualified(p: Path) -> str:
    return "cora." + ".".join(p.relative_to(CORA_ROOT).with_suffix("").parts)


def _scanned_files() -> list[Path]:
    return sorted(tracked_python_files())


def _property_keys(tree: ast.AST) -> list[tuple[int, str]]:
    """For every dict literal with a ``"properties"`` key, yield (lineno, prop_key)."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=False):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and key.value == "properties"
                and isinstance(value, ast.Dict)
            ):
                for prop_k in value.keys:
                    if isinstance(prop_k, ast.Constant) and isinstance(prop_k.value, str):
                        out.append((prop_k.lineno, prop_k.value))
    return out


@pytest.mark.architecture
@pytest.mark.parametrize("path", _scanned_files(), ids=_qualified)
def test_schema_property_keys_have_no_unit_suffix(path: Path) -> None:
    qualified = _qualified(path)
    tree = ast.parse(path.read_text())
    violations: list[str] = []
    for lineno, key in _property_keys(tree):
        if not _UNIT_SUFFIX.search(key):
            continue
        if f"{qualified}:{key}" in GRANDFATHERED_PROPERTY_KEYS:
            continue
        violations.append(f"line {lineno}: properties[{key!r}]")
    assert not violations, (
        f"{qualified} declares JSON Schema properties with unit "
        f"suffixes:\n  " + "\n  ".join(violations) + "\n"
        "Per docs/reference/conventions.md, units live in the "
        "`unit: {system, code}` annotation alongside the field, not "
        "baked into the property key."
    )


@pytest.mark.architecture
def test_grandfathered_property_keys_still_have_unit_suffix() -> None:
    """``GRANDFATHERED_PROPERTY_KEYS`` entries must still carry a unit suffix.

    Drift catcher: once a rename moves a key to its unit-agnostic
    form, its allowlist entry becomes dead weight. Re-running the
    unit-suffix regex here forces the entry to be removed alongside
    the rename.
    """
    for entry in GRANDFATHERED_PROPERTY_KEYS:
        qualified, _, key = entry.partition(":")
        parts = qualified.split(".")
        assert parts[0] == "cora", f"{entry}: must start with 'cora.'"
        path = CORA_ROOT.joinpath(*parts[1:]).with_suffix(".py")
        assert path.is_file(), f"{entry}: file no longer exists; remove allowlist"
        tree = ast.parse(path.read_text())
        found_keys = {k for _, k in _property_keys(tree)}
        assert key in found_keys, (
            f"{entry}: property key no longer present; remove allowlist entry "
            "(unit-suffix rename shipped)"
        )
        assert _UNIT_SUFFIX.search(key), (
            f"{entry}: key no longer matches a unit suffix; remove allowlist entry"
        )

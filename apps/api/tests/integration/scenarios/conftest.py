"""Scenario-level conftest.

Validates every scenario file's module docstring header (cluster +
archetype + bc_primary + bc_touches) at pytest collection time. The
docs/scenarios/ surface reads the same metadata at docs build time;
catching schema errors here closes the loop on test write rather than
on the next docs build.

Schema and closed vocabularies live in scripts/scenarios_meta.py.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

_SCENARIOS_DIR = Path(__file__).resolve().parent
_SCENARIOS_META_PATH = _SCENARIOS_DIR.parents[4] / "scripts" / "scenarios_meta.py"


def _load_scenarios_meta() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scenarios_meta", _SCENARIOS_META_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load scenarios_meta from {_SCENARIOS_META_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["scenarios_meta"] = module
    spec.loader.exec_module(module)
    return module


_scenarios_meta = _load_scenarios_meta()


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Fail the session if any collected scenario has an invalid header."""
    seen_files: set[Path] = set()
    errors: list[str] = []
    for item in items:
        path = Path(str(item.path))
        if path.parent != _SCENARIOS_DIR or path in seen_files:
            continue
        seen_files.add(path)
        try:
            doc = _scenarios_meta.extract_docstring(path)
            _scenarios_meta.parse_metadata(path, doc)
        except _scenarios_meta.ScenarioHeaderError as exc:
            errors.append(str(exc))
    if errors:
        pytest.exit(
            "scenario header validation failed:\n  " + "\n  ".join(errors),
            returncode=2,
        )

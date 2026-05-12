"""Shared roots and helpers for architecture fitness-function tests.

These tests run alongside the rest of the suite (`pytest` picks
them up automatically) but enforce structural invariants the
import graph + AST + filesystem can prove. Tach (`tach.toml` at
the apps/api root) handles dependency-graph rules; everything
under this directory handles the rules tach can't express:
slice file contracts, decider purity, completeness-of-wiring.

`SRC_ROOT` is computed relative to this file so tests work
whether pytest is invoked from `apps/api/` (the Makefile target)
or from the repository root (CI).
"""

from pathlib import Path

# tests/architecture/conftest.py -> apps/api/
_API_ROOT = Path(__file__).resolve().parents[2]

SRC_ROOT = _API_ROOT / "src"
CORA_ROOT = SRC_ROOT / "cora"

BCS: tuple[str, ...] = (
    "access",
    "equipment",
    "recipe",
    "run",
    "subject",
    "trust",
)

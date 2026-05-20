"""OpenAPI snapshot drift test.

Asserts that the committed `apps/api/openapi.json` matches what
`create_app().openapi()` produces right now. Any change to a route's
path, method, parameter shape, request body, response schema, or
operation metadata fails this test until the snapshot is regenerated.

This makes API surface changes:
- visible in PR diffs (reviewers see exactly what shifted)
- intentional (regen is a deliberate step, not a side effect)
- consumable as a static artifact (docs site, external integrators,
  generator-based client SDKs)

To regenerate after an intentional change:

    make openapi-snapshot

The snapshot is serialised with `sort_keys=True` and `indent=2` so
the on-disk form is deterministic across machines and stable under
git diff. Comparison loads both sides as Python dicts so dict key
ordering differences within the FastAPI-generated spec don't cause
false negatives.
"""

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

import json
from pathlib import Path

from cora.api.main import create_app

_SNAPSHOT_PATH = Path(__file__).resolve().parents[2] / "openapi.json"


def test_committed_openapi_snapshot_matches_live_spec() -> None:
    """Committed openapi.json equals `create_app().openapi()` right now."""
    live_spec = create_app().openapi()
    committed = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert committed == live_spec, (
        f"OpenAPI snapshot drift detected at {_SNAPSHOT_PATH.name}. "
        "Run `make openapi-snapshot` to regenerate, then review the diff."
    )

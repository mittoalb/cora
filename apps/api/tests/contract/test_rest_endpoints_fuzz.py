"""REST property-fuzz across the same 5 create-style endpoints as
`test_mcp_tools_fuzz.py`.

Mirrors the MCP fuzz harness on the REST surface. Pulls the request
model's JSON Schema via Pydantic `model_json_schema()`, feeds it to
`hypothesis-jsonschema`, and asserts:

  1. Schema-conforming inputs never produce HTTP 422 (Pydantic body
     validation failure). 400 (domain rejection), 403 (authz), or 2xx
     are all acceptable; 422 alone would mean the request model has
     drifted from the schema we sampled.
  2. On 2xx responses, the body validates against the response model's
     JSON Schema (output drift catcher).

Why this earns its keep alongside `test_mcp_tools_fuzz.py`: Pydantic
generates the wire-visible request schema via a Draft 2020-12 path,
while FastMCP derives MCP `inputSchema` via its own code path. Fuzzing
BOTH surfaces independently catches request-shape drift on whichever
surface introduces it.

Same allowlist as the MCP harness, intentional: lets the two harnesses
form a contract-symmetry pair. Differential REST/MCP outcome parity
remains the job of `test_*_differential.py`.

Out of scope for v1: the `Idempotency-Key` header. Every endpoint here
declares it as an optional header outside the request body model, so
`model_json_schema()` does not surface it and fuzzing the body alone
cannot reach replay/conflict paths. Idempotency-Key contract behaviour
(same key + same body returns cached response, same key + different
body returns 422) is exercised by per-slice tests under
`tests/integration/`. A dedicated stateful fuzz over the header is the
trigger to revisit if a replay-class drift slips through.

See [[project_testing_techniques_research]] Corpus 3 for the open-
frontier framing on property-fuzz for two-surface architectures.
"""

from __future__ import annotations

# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
from copy import deepcopy
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis_jsonschema import from_schema
from jsonschema import Draft7Validator

from cora.access.features.register_actor.route import (
    RegisterActorRequest,
    RegisterActorResponse,
)
from cora.api.main import create_app
from cora.equipment.features.define_family.route import (
    DefineFamilyRequest,
    DefineFamilyResponse,
)
from cora.recipe.features.define_capability.route import (
    DefineCapabilityRequest,
    DefineCapabilityResponse,
)
from cora.trust.features.define_surface.route import (
    DefineSurfaceRequest,
    DefineSurfaceResponse,
)
from cora.trust.features.define_zone.route import (
    DefineZoneRequest,
    DefineZoneResponse,
)

if TYPE_CHECKING:
    from pydantic import BaseModel


def _strip_schema_dialect(schema: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy with the top-level `$schema` field removed.

    `hypothesis-jsonschema` raises on `$schema` values it doesn't
    recognise (Pydantic emits the Draft 2020-12 URI). Stripping it
    forces the Draft 07 code path, which is correct for the schema
    constructs Pydantic actually emits for these models.
    """
    clone = deepcopy(schema)
    clone.pop("$schema", None)
    return clone


_ENDPOINTS: tuple[tuple[str, str, type[BaseModel], type[BaseModel]], ...] = (
    ("register_actor", "/actors", RegisterActorRequest, RegisterActorResponse),
    ("define_zone", "/zones", DefineZoneRequest, DefineZoneResponse),
    ("define_family", "/families", DefineFamilyRequest, DefineFamilyResponse),
    ("define_capability", "/capabilities", DefineCapabilityRequest, DefineCapabilityResponse),
    ("define_surface", "/surfaces", DefineSurfaceRequest, DefineSurfaceResponse),
)


@pytest.mark.contract
@pytest.mark.parametrize(
    "tool_name,url,request_model,response_model",
    _ENDPOINTS,
    ids=[name for name, *_ in _ENDPOINTS],
)
def test_rest_endpoint_accepts_schema_conforming_input(
    tool_name: str,
    url: str,
    request_model: type[BaseModel],
    response_model: type[BaseModel],
) -> None:
    """Schema-conforming inputs never trip Pydantic's 422 validator.

    Two assertions per generated example:
      1. Response status is NEVER 422. 422 means Pydantic body
         validation rejected an input the request model's own
         `model_json_schema()` declared valid: that is the drift this
         harness exists to catch. 400 (domain rejection), 403 (authz),
         and 2xx are all acceptable outcomes.
      2. On 2xx, the response body validates against the response
         model's JSON Schema. Catches response-shape drift.

    TestClient is hoisted outside the Hypothesis property body so each
    parametrised case pays one lifespan startup, not 50.
    """
    input_schema = _strip_schema_dialect(request_model.model_json_schema())
    output_schema = _strip_schema_dialect(response_model.model_json_schema())
    strategy = from_schema(input_schema)

    with TestClient(create_app()) as client:

        @given(arguments=strategy)
        @settings(
            max_examples=50,
            deadline=None,
            suppress_health_check=[HealthCheck.function_scoped_fixture],
        )
        def _property(arguments: dict[str, Any]) -> None:
            response = client.post(url, json=arguments)

            assert response.status_code != 422, (
                f"[{tool_name}] schema-conforming input rejected with 422: "
                f"args={arguments!r} body={response.json()!r}"
            )

            if 200 <= response.status_code < 300:
                Draft7Validator(output_schema).validate(response.json())

        _property()


_NEGATIVE_CASES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("register_actor", "/actors", {"name": 12345}),
    ("define_zone", "/zones", {"name": 12345}),
    ("define_family", "/families", {"name": 12345, "affordances": ["not_a_real_affordance"]}),
    ("define_capability", "/capabilities", {"name": 12345}),
    ("define_surface", "/surfaces", {"kind": "not_a_real_surface_kind"}),
)


@pytest.mark.contract
@pytest.mark.parametrize(
    "tool_name,url,arguments",
    _NEGATIVE_CASES,
    ids=[name for name, *_ in _NEGATIVE_CASES],
)
def test_rest_endpoint_rejects_schema_violating_input(
    tool_name: str, url: str, arguments: dict[str, Any]
) -> None:
    """A schema-violating input MUST surface as HTTP 422.

    Proves the positive property above isn't passing vacuously. If
    Pydantic ever stops validating request bodies against the declared
    model entirely, the positive test would silently pass on garbage
    inputs forever; this companion test fires the negative case to show
    validation is still alive.
    """
    with TestClient(create_app()) as client:
        response = client.post(url, json=arguments)

    assert response.status_code == 422, (
        f"[{tool_name}] schema-violating input was NOT rejected with 422: "
        f"args={arguments!r} status={response.status_code} body={response.json()!r}"
    )

"""Unit tests for the `get_practice` query handler.

Mirrors `test_get_method_handler.py`. Round-trip define + get
verifies fold-on-read returns the registered Practice with the
right method_id and site_id.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from cora.recipe import RecipeHandlers, UnauthorizedError, wire_recipe
from cora.recipe.aggregates.practice import Practice, PracticeName, PracticeStatus
from cora.recipe.features import define_practice, get_practice
from cora.recipe.features.define_practice import DefinePractice
from cora.recipe.features.get_practice import GetPractice
from tests.unit._helpers import RecordingAuthorize, build_deps

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=UTC)
_NEW_ID = UUID("01900000-0000-7000-8000-00000000bc01")
_EVENT_ID = UUID("01900000-0000-7000-8000-00000000bc02")
_PRINCIPAL_ID = UUID("01900000-0000-7000-8000-000000000099")
_CORRELATION_ID = UUID("01900000-0000-7000-8000-0000000000aa")
_METHOD_ID = UUID("01900000-0000-7000-8000-000000000111")
_SITE_ID = UUID("01900000-0000-7000-8000-000000000222")


@pytest.mark.unit
async def test_handler_returns_practice_for_known_id() -> None:
    """Round-trip: define + get."""
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    await define_practice.bind(deps)(
        DefinePractice(
            name="APS Standard Tomography",
            method_id=_METHOD_ID,
            site_id=_SITE_ID,
        ),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    handler = get_practice.bind(deps)
    view = await handler(
        GetPractice(practice_id=_NEW_ID),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert view is not None
    assert view.practice == Practice(
        id=_NEW_ID,
        name=PracticeName("APS Standard Tomography"),
        method_id=_METHOD_ID,
        site_id=_SITE_ID,
        status=PracticeStatus.DEFINED,
    )
    # In-memory deps have no pool -> projection-sourced timestamps absent.
    assert view.timestamps is None


@pytest.mark.unit
async def test_handler_returns_none_for_unknown_id() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handler = get_practice.bind(deps)
    view = await handler(
        GetPractice(practice_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )
    assert view is None


@pytest.mark.unit
async def test_handler_authorizes_with_query_name_and_default_conduit() -> None:
    tracking = RecordingAuthorize()
    deps = build_deps(ids=[_NEW_ID], now=_NOW, authorize=tracking)

    handler = get_practice.bind(deps)
    await handler(
        GetPractice(practice_id=uuid4()),
        principal_id=_PRINCIPAL_ID,
        correlation_id=_CORRELATION_ID,
    )

    assert tracking.calls == [(_PRINCIPAL_ID, "GetPractice", UUID(int=0), UUID(int=0))]


@pytest.mark.unit
async def test_handler_raises_unauthorized_on_deny() -> None:
    deps = build_deps(ids=[_NEW_ID], now=_NOW, deny=True)

    handler = get_practice.bind(deps)
    with pytest.raises(UnauthorizedError) as exc_info:
        await handler(
            GetPractice(practice_id=uuid4()),
            principal_id=_PRINCIPAL_ID,
            correlation_id=_CORRELATION_ID,
        )
    assert exc_info.value.reason == "denied for test"


@pytest.mark.unit
def test_wire_recipe_includes_get_practice() -> None:
    deps = build_deps(ids=[_NEW_ID, _EVENT_ID], now=_NOW)
    handlers = wire_recipe(deps)
    assert isinstance(handlers, RecipeHandlers)
    assert callable(handlers.get_practice)

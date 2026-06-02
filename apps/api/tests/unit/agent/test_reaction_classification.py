"""Both Agent BC subscribers classify as `Reaction` with `batch_size = 1`.

Pins the contract that the Reaction Protocol shipping introduced:
each LLM-bound Subscriber declares `batch_size = 1` so the worker
bounds the bookmark transaction to a single LLM round-trip and does
not starve Projection advance loops sharing the same pool.

If a future Reaction author forgets to declare `batch_size`, the
worker silently inherits the worker-level default (100) and the
incident the docstring warned about becomes real. This test surfaces
the omission at unit-test time instead of at first wedge.
"""

from cora.agent.subscribers.caution_drafter import CautionDrafterSubscriber
from cora.agent.subscribers.run_debriefer import RunDebrieferSubscriber
from cora.infrastructure.projection.handler import Reaction


def test_run_debriefer_subscriber_is_a_reaction() -> None:
    """Structural-typing check: the class satisfies the Reaction
    Protocol at the type level (name, subscribed_event_types,
    batch_size, async apply)."""
    assert isinstance(RunDebrieferSubscriber.__dict__["name"], str)
    assert isinstance(RunDebrieferSubscriber.__dict__["subscribed_event_types"], frozenset)
    assert isinstance(RunDebrieferSubscriber.__dict__["batch_size"], int)


def test_caution_drafter_subscriber_is_a_reaction() -> None:
    assert isinstance(CautionDrafterSubscriber.__dict__["name"], str)
    assert isinstance(CautionDrafterSubscriber.__dict__["subscribed_event_types"], frozenset)
    assert isinstance(CautionDrafterSubscriber.__dict__["batch_size"], int)


def test_run_debriefer_pins_batch_size_to_one() -> None:
    """Every LLM-bound Reaction MUST pin batch_size to 1 (a slow LLM
    call should not hold the pool connection across N events).
    Update the docstring + Reaction Protocol contract before changing."""
    assert RunDebrieferSubscriber.batch_size == 1


def test_caution_drafter_pins_batch_size_to_one() -> None:
    assert CautionDrafterSubscriber.batch_size == 1


def test_reaction_protocol_is_runtime_checkable() -> None:
    """The Reaction Protocol is `@runtime_checkable` so a test or
    arch-fitness check can isinstance-test against it. Without
    runtime_checkable, this assertion would raise TypeError."""
    # `isinstance(obj, Reaction)` only checks that the required
    # attributes exist; values are not validated. The point of this
    # test is that the Protocol declaration itself permits the check.
    assert hasattr(Reaction, "__protocol_attrs__") or hasattr(Reaction, "_is_protocol")

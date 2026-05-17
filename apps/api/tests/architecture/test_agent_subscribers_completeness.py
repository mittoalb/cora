"""Pin: every subscriber file in `cora.agent.subscribers/` is registered.

Background: the post-review audit caught `agent/subscribers/__init__.py`
declaring "today the registry has one subscriber" after
CautionDrafterSubscriber had already shipped, AND the
`_subscribers.register_agent_subscribers` glue listing only the
old subscriber. A third agent would silently regress the same way
without an architectural pin.

Rule: for every `cora/agent/subscribers/<name>.py` (excluding
`__init__.py` and leading-underscore helpers), the file MUST
export a `make_<name>_subscriber` factory AND that factory MUST be
called inside `cora/agent/_subscribers.py`'s
`register_agent_subscribers` function.

The pin scans `_subscribers.py` with AST for `ast.Call` nodes whose
`func` is the expected name; this catches the entire dependency
direction (registry -> subscriber factory) even when imports use
aliases.

Whenever a third subscriber lands, this test passes only after
(a) adding the module under `subscribers/`, (b) exporting a
`make_<name>_subscriber` factory, and (c) registering it in
`_subscribers.py`. The named widening triggers in the design memo
(3rd subscriber / >50ms blocking / cross-subscriber ordering) all
land at the same boundary as a new subscriber file.
"""

import ast
from pathlib import Path

import pytest

from tests.architecture.conftest import CORA_ROOT

_SUBSCRIBERS_DIR = CORA_ROOT / "agent" / "subscribers"
_REGISTRY_FILE = CORA_ROOT / "agent" / "_subscribers.py"


def _subscriber_modules() -> list[Path]:
    """Every concrete subscriber module under `cora/agent/subscribers/`.

    Excludes `__init__.py` and leading-underscore helpers (those are
    intra-package machinery, not subscribers themselves).
    """
    out: list[Path] = []
    for path in sorted(_SUBSCRIBERS_DIR.glob("*.py")):
        if path.name == "__init__.py" or path.name.startswith("_"):
            continue
        out.append(path)
    return out


def _called_function_names(tree: ast.AST) -> set[str]:
    """Names called as `Name(...)` or `module.Name(...)` anywhere in the tree."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                out.add(func.id)
            elif isinstance(func, ast.Attribute):
                out.add(func.attr)
    return out


def _module_stem(path: Path) -> str:
    return path.stem


@pytest.mark.architecture
@pytest.mark.parametrize("path", _subscriber_modules(), ids=_module_stem)
def test_subscriber_factory_is_registered(path: Path) -> None:
    """Each subscriber's `make_*_subscriber` factory is called in the registry."""
    stem = _module_stem(path)
    expected_factory = f"make_{stem}_subscriber"

    # 1. Subscriber file actually exports the expected factory.
    subscriber_tree = ast.parse(path.read_text())
    defined: set[str] = set()
    for node in ast.walk(subscriber_tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            defined.add(node.name)
    assert expected_factory in defined, (
        f"cora.agent.subscribers.{stem} does not define {expected_factory}; "
        "every subscriber module must export a "
        "`make_<module-stem>_subscriber(deps: Kernel) -> <Subscriber>` factory."
    )

    # 2. _subscribers.py calls the factory (any path: bare Name(...) or
    # module.attr(...)).
    registry_tree = ast.parse(_REGISTRY_FILE.read_text())
    called = _called_function_names(registry_tree)
    assert expected_factory in called, (
        f"cora.agent._subscribers does not call {expected_factory}; "
        f"register_agent_subscribers must wire every subscriber under "
        "cora.agent.subscribers/ into the projection-worker registry."
    )

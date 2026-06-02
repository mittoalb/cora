"""Both Recipe BC and Operation BC routes files must register a 422 exception handler.

Six Recipe rejection classes (per [[project-recipe-aggregate-design]] Rejections)
map to HTTP 422 (parse-shape / schema-cross-check failures past the Pydantic
boundary). Without an explicit `_handle_unprocessable` handler the unmapped
raise silently falls through to the default 500. This fitness pins the
handler registration so a future routes-file refactor cannot accidentally
drop it.

Operation BC currently has no 422-mapped Recipe errors at this commit
boundary; the assertion against `cora/operation/routes.py` is gated to
SKIP until that BC gains its own 422-family errors in a downstream commit.
The Recipe BC assertion is unconditional.
"""

import ast
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RECIPE_ROUTES = _REPO_ROOT / "src" / "cora" / "recipe" / "routes.py"
_OPERATION_ROUTES = _REPO_ROOT / "src" / "cora" / "operation" / "routes.py"


def _has_422_handler(path: Path) -> bool:
    """Return True if the module text references the FastAPI 422 status constant.

    Looks for either the modern `HTTP_422_UNPROCESSABLE_CONTENT` constant
    or the deprecated `HTTP_422_UNPROCESSABLE_ENTITY` alias in the file
    content; this is the load-bearing surface (the `_handle_unprocessable`
    function body uses it). Either the helper function or an inline
    reference in a routes-level handler satisfies the gate.
    """
    if not path.is_file():
        return False
    text = path.read_text()
    return "HTTP_422_UNPROCESSABLE_CONTENT" in text or "HTTP_422_UNPROCESSABLE_ENTITY" in text


def _module_imports_unprocessable_helper(path: Path) -> bool:
    """Return True if the file defines a `_handle_unprocessable` function."""
    if not path.is_file():
        return False
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_handle_unprocessable":
            return True
        if isinstance(node, ast.FunctionDef) and node.name == "_handle_unprocessable":
            return True
    return False


@pytest.mark.architecture
def test_recipe_routes_registers_422_handler() -> None:
    """Recipe routes.py exposes a 422 handler used by 4 Recipe error classes.

    Without this handler, InvalidRecipeStepShapeError /
    RecipeBindingReferencesUnknownParameterError /
    RecipeRequiresCapabilityParametersSchemaError / UnboundRecipeBindingError
    fall through to 500 instead of the documented 422.
    """
    assert _RECIPE_ROUTES.is_file(), f"missing routes file: {_RECIPE_ROUTES}"
    assert _has_422_handler(_RECIPE_ROUTES), (
        f"{_RECIPE_ROUTES} must reference HTTP_422_UNPROCESSABLE_ENTITY (Recipe BC "
        "has 4 errors mapped to 422 per the Recipe aggregate design memo)."
    )
    assert _module_imports_unprocessable_helper(_RECIPE_ROUTES), (
        f"{_RECIPE_ROUTES} must define a `_handle_unprocessable` function so "
        "FastAPI add_exception_handler calls register the 422 mapping."
    )


@pytest.mark.architecture
def test_operation_routes_registers_422_handler_when_needed() -> None:
    """Operation routes.py 422-handler gate; skipped until the BC needs one.

    Recipe expansion at register_procedure_from_recipe time can raise
    RecipeBindingsStaleAgainstCurrentCapabilityError (per memo Rejections)
    which must map to 422 from Operation BC routes. Until that handler
    lands the check is skipped; do not delete this test, gate it.
    """
    if not _OPERATION_ROUTES.is_file():
        pytest.skip(f"missing routes file: {_OPERATION_ROUTES}")
    text = _OPERATION_ROUTES.read_text()
    if "RecipeBindings" not in text and "RecipeExpansion" not in text:
        pytest.skip(
            "Operation BC has no Recipe-tier 422 errors registered yet; "
            "the handler lands when the Operation BC slice rewrite imports "
            "the Recipe-tier error classes."
        )
    assert _has_422_handler(_OPERATION_ROUTES), (
        f"{_OPERATION_ROUTES} imports Recipe-tier error classes but does not "
        "reference HTTP_422_UNPROCESSABLE_ENTITY; add a `_handle_unprocessable` "
        "helper and register the Recipe-tier 422 errors."
    )

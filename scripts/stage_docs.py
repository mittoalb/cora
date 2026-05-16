"""Stage repo-root docs into the mkdocs build directory.

Copies CONTRIBUTING.md -> docs/reference/contributing.md. The docs landing
page (docs/index.md) is hand-crafted and source-controlled; the GitHub
README serves a different audience (cloners) and is not staged.

Link rewriting still happens in-memory at build time via the mkdocs hook
in scripts/mkdocs_hooks.py.

Run from the repo root:  python scripts/stage_docs.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
STAGED_CONTRIBUTING = DOCS_DIR / "reference" / "contributing.md"


def main() -> None:
    STAGED_CONTRIBUTING.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REPO_ROOT / "CONTRIBUTING.md", STAGED_CONTRIBUTING)
    print(f"Staged contributing.md into {STAGED_CONTRIBUTING.parent}")


if __name__ == "__main__":
    main()

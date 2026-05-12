"""Stage repo-root docs into the mkdocs build directory.

Copies README.md -> docs/index.md and CONTRIBUTING.md -> docs/contributing.md.
Does NOT modify the source files in docs/. Link rewriting happens in-memory
at build time via the mkdocs hook in scripts/mkdocs_hooks.py.

Run from the repo root:  python scripts/stage_docs.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"


def main() -> None:
    shutil.copyfile(REPO_ROOT / "README.md", DOCS_DIR / "index.md")
    shutil.copyfile(REPO_ROOT / "CONTRIBUTING.md", DOCS_DIR / "contributing.md")
    print(f"Staged index.md and contributing.md into {DOCS_DIR}")


if __name__ == "__main__":
    main()

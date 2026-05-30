"""MkDocs build-time hooks.

**Link rewriting** (`on_page_markdown`). Rewrites markdown links
in-memory so the static site at xmap.github.io/cora/ resolves
correctly without mutating the source files in docs/.

  1. The staged reference/contributing.md (mirrored from /CONTRIBUTING.md
     at build time) has paths that are repo-root-relative. They are
     rewritten to either an intra-site mkdocs path (when the target is a
     docs/ page) or a GitHub blob URL (when the target is a repo file
     outside docs/).

  2. Every other page in docs/ is page-aware: links that resolve inside
     docs/ are left alone (mkdocs handles relative intra-site links
     natively); links that resolve outside docs/ are rewritten to GitHub
     blob URLs (or to the staged contributing page for the
     ../CONTRIBUTING.md special case).

Links containing /.claude/ (private auto-memory) are stripped to plain
text.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

REPO_BLOB = "https://github.com/xmap/cora/blob/main/"
HOOK_DIR = Path(__file__).resolve().parent
REPO_ROOT = HOOK_DIR.parent
DOCS_DIR = REPO_ROOT / "docs"
STAGED_CONTRIBUTING_SRC_URI = "reference/contributing.md"

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _rewrite_in_page(page_src_uri: str, markdown: str) -> str:
    is_staged = page_src_uri == STAGED_CONTRIBUTING_SRC_URI
    page_path_in_docs = Path(page_src_uri)
    page_dir_in_docs = page_path_in_docs.parent
    # Number of "../" steps to climb from the page back to docs/ root.
    depth_to_docs_root = (
        0 if str(page_dir_in_docs) == "." else len(page_dir_in_docs.parts)
    )
    up_to_docs_root = "../" * depth_to_docs_root

    def _rewrite(match: re.Match[str]) -> str:
        original = match.group(0)
        label, target = match.group(1), match.group(2)

        # Leave external links, anchors, and mailto alone.
        if target.startswith(("http://", "https://", "#", "mailto:")):
            return original

        # Strip links into private auto-memory.
        if "/.claude/" in target:
            return label

        # Split off any anchor fragment.
        if "#" in target:
            path_part, anchor = target.split("#", 1)
            anchor = "#" + anchor
        else:
            path_part, anchor = target, ""

        if not path_part:
            return original

        if is_staged:
            # Staged reference/contributing.md mirrors /CONTRIBUTING.md, so
            # paths in the source are repo-root-relative. Rewrite them to be
            # relative to the staged page's location (docs/reference/).
            cleaned = path_part
            while cleaned.startswith("../"):
                cleaned = cleaned[3:]
            while cleaned.startswith("./"):
                cleaned = cleaned[2:]

            if cleaned == "CONTRIBUTING.md":
                return f"[{label}](contributing.md{anchor})"
            if cleaned.startswith("docs/"):
                cleaned = cleaned[len("docs/") :]
                if cleaned == "" or cleaned.endswith("/"):
                    return f"[{label}]({up_to_docs_root}index.md{anchor})"
                return f"[{label}]({up_to_docs_root}{cleaned}{anchor})"

            return f"[{label}]({REPO_BLOB}{cleaned}{anchor})"

        # Non-staged page in docs/: paths are page-relative mkdocs links.
        # Resolve to determine whether the target lives in docs/.
        page_dir_abs = (DOCS_DIR / page_dir_in_docs).resolve()
        try:
            resolved = (page_dir_abs / path_part).resolve()
        except (OSError, RuntimeError):
            return original

        # Inside docs/ -> mkdocs handles natively, leave alone.
        try:
            resolved.relative_to(DOCS_DIR.resolve())
            return original
        except ValueError:
            pass

        # Outside docs/ but inside the repo: rewrite.
        try:
            rel_in_repo = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
        except ValueError:
            return original

        if rel_in_repo == "CONTRIBUTING.md":
            return f"[{label}]({up_to_docs_root}reference/contributing.md{anchor})"

        return f"[{label}]({REPO_BLOB}{rel_in_repo}{anchor})"

    return LINK_RE.sub(_rewrite, markdown)


def on_page_markdown(
    markdown: str,
    *,
    page: Any,
    config: Any,  # noqa: ARG001
    files: Any,  # noqa: ARG001
) -> str:
    return _rewrite_in_page(page.file.src_uri, markdown)

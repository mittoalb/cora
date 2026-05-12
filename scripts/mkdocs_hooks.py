"""MkDocs build-time hooks.

Rewrites markdown links in-memory so the static site at xmap.github.io/cora/
resolves correctly without mutating the source files in docs/:

    - Repo-relative paths (apps/, infra/, .github/, etc.) -> https://github.com/xmap/cora/blob/main/...
    - ../README.md -> index.md   (the staged copy of the README)
    - ../CONTRIBUTING.md -> contributing.md   (the staged copy)
    - docs/foo.md -> foo.md   (intra-site)
    - Links containing /.claude/ (private auto-memory) are stripped to plain text

Registered in mkdocs.yml under `hooks:`.
"""

from __future__ import annotations

import re
from typing import Any

REPO_BLOB = "https://github.com/xmap/cora/blob/main/"

# Files that exist in the published mkdocs site (matches mkdocs.yml nav).
INTRA_SITE = {
    "index.md",
    "architecture.md",
    "stack.md",
    "glossary.md",
    "contributing.md",
}

LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _rewrite(match: re.Match[str]) -> str:
    label, target = match.group(1), match.group(2)

    # Leave external links and anchors alone.
    if target.startswith(("http://", "https://", "#", "mailto:")):
        return match.group(0)

    # Strip links into private auto-memory.
    if "/.claude/" in target:
        return label

    # Split off any anchor fragment (e.g. file.md#section).
    if "#" in target:
        path_part, anchor = target.split("#", 1)
        anchor = "#" + anchor
    else:
        path_part, anchor = target, ""

    # Normalise: drop leading ./ and ../ segments.
    cleaned = path_part
    while cleaned.startswith("../"):
        cleaned = cleaned[3:]
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]

    # Map repo-root docs to their published-site filenames.
    if cleaned == "README.md":
        return f"[{label}](index.md{anchor})"
    if cleaned == "CONTRIBUTING.md":
        return f"[{label}](contributing.md{anchor})"

    # If the link is into docs/, strip the prefix so it resolves intra-site.
    if cleaned.startswith("docs/"):
        cleaned = cleaned[len("docs/") :]

    if cleaned in INTRA_SITE:
        return f"[{label}]({cleaned}{anchor})"

    # Anything else: rewrite as a GitHub blob URL.
    return f"[{label}]({REPO_BLOB}{cleaned}{anchor})"


def on_page_markdown(
    markdown: str,
    *,
    page: Any,  # noqa: ARG001
    config: Any,  # noqa: ARG001
    files: Any,  # noqa: ARG001
) -> str:
    return LINK_RE.sub(_rewrite, markdown)

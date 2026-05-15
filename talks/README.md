# Talks

Slidev decks. Each subdirectory is one deck and gets built+published by
[.github/workflows/docs.yml](../.github/workflows/docs.yml) under
`https://xmap.github.io/cora/talks/<slug>/`. The folder name is the slug; it
becomes the URL path and the PDF filename forever.

## Add a new deck

1. Create `talks/<slug>/` (see naming below).
2. `cd talks/<slug> && npm init slidev@latest` (or copy `2026-maxiv-fov/` as a
   template).
3. Commit sources. CI builds and deploys on push to `main`.

That's it. The workflow auto-discovers any directory with a `package.json`.

## Naming convention

Year-first, kebab-case: **`YYYY-<venue>-<short-tag>`** (e.g., `2026-maxiv-fov`).

Two reasons:

- `ls talks/` sorts chronologically. Easy to scan "what did I do in 2026?"
- Matches the [Slidev community precedent](https://github.com/antfu/talks) and
  Jekyll/al-folio academic templates (`YYYY-MM-DD-talk-name`).

Examples:

| Slug | Venue | Year |
|---|---|---|
| `2026-maxiv-fov` | MAX IV Fields of View workshop | 2026 |
| `2026-aps-users` | APS Users Meeting | 2026 |
| `2027-icalepcs` | ICALEPCS conference | 2027 |

Rules:

- Lowercase kebab-case (no `_`, no spaces, no caps).
- Under 30 chars total. URLs and PDF filenames look bad long.
- Year alone is fine for now; add `-MM` if you ever ship two decks in the same
  month at the same venue (`2027-06-aps-users` vs `2027-11-aps-users`).
- For evergreen decks reused across venues unchanged, drop the venue and use
  `<year>-<topic>` (e.g., `2026-cora-intro`); re-tune the slides per venue and
  bump the year on each rebuild.

## Per-deck README

Each `talks/<slug>/` folder has its own `README.md` covering:

- Lead motivator (one sentence).
- Audience tuning notes (which slides to swap per audience).
- Customization checklist before presenting.

[2026-maxiv-fov/README.md](2026-maxiv-fov/README.md) is a working template.

## What gets tracked

Sources only: `slides.md`, `package.json`, `package-lock.json`, `style.css`,
`public/`, `README.md`. Build artifacts (`dist/`, `node_modules/`, exported
`*.pdf`) are gitignored at the repo root.

## Listing page

[docs/talks.md](../docs/talks.md) is the public index. Add an entry there
when you ship a new deck.

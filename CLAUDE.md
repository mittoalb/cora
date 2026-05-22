# Repo guidance

This file is read by Claude Code (and other agents that respect `CLAUDE.md`). Keep it as a pointer file, not a long doc; the real conventions live in `docs/reference/`.

## Conventions

- **Codebase layout, naming, BC structure, patterns**: [docs/reference/](docs/reference/index.md)
- **Identifiers, units, personal data, schema-validated values, documentation**: [docs/reference/conventions.md](docs/reference/conventions.md)
- **Docstring + comment + test-doc style specifically**: [docs/reference/conventions.md#documentation](docs/reference/conventions.md#documentation)
- **Glossary**: [docs/reference/glossary.md](docs/reference/glossary.md)

## Hard rules carried into every change

- No phase / iteration / audit tags (`Phase 8f-d`, `Iter B-3`, `DLM-A`, `audit-2026-...`) in source. Git log and `project_phase_plan.md` are the right home.
- No emoji anywhere in source — comments, docstrings, log strings, error messages, `Field(description=...)`.
- No em dashes in user-facing prose; use commas, colons, or rephrase.
- Default to no `#` comments. Add one only when the WHY is non-obvious.
- Test names carry scenarios (`test_<subject>_<scenario>_<expectation>`); per-test docstrings stay rare.

## Commits

One-line subject, body explains WHY. Recent commits set the tone — `git log --oneline -10`.

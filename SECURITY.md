# Security Policy

## Supported versions

CORA is pre-1.0 (active development; APIs and schema still subject to change). Only the `main` branch receives security fixes. There are no LTS lines.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Use **GitHub's private vulnerability reporting** for this repository:

1. Go to the [Security tab](https://github.com/xmap/cora/security) of the repo.
2. Click **Report a vulnerability**.
3. Fill in the form with as much detail as you can:
   - the affected component (BC, port, adapter, slice, migration, etc.)
   - the impact (data exposure, privilege escalation, denial of service, etc.)
   - reproduction steps or a proof-of-concept
   - the commit hash you tested against

You will receive an acknowledgement within **5 business days**. We aim to issue a fix or a public advisory within **30 days** of acknowledgement, depending on severity and complexity.

## Scope

In scope:
- The CORA application itself: handlers, ports, adapters, event store, projections, API surfaces (REST + MCP), authentication wiring, authorisation port.
- Migrations and database role configuration in `infra/atlas/`.
- CI, build, and release tooling in `.github/workflows/` and `Makefile`.

Out of scope:
- Vulnerabilities in upstream dependencies (report those upstream; CORA pulls security fixes via Dependabot).
- Misconfiguration of a downstream deployment that does not front the API with a verifying proxy as documented in [docs/reference/runtime.md](docs/reference/runtime.md). The application's `X-Principal-Id` header trust contract is documented; deploying without a verifying proxy is a deployment misconfiguration, not an application vulnerability.
- Issues that require an authenticated principal already holding sufficient privilege (those are bugs, not security vulnerabilities; please open a normal issue).

## Hardening notes

If you are deploying CORA, the production gates are:

- `DATABASE_URL` connects as the `cora_app` role: `events` and `entries_*` tables are INSERT-only (UPDATE / DELETE / TRUNCATE revoked); `proj_*` projection tables get full DML. Migrations run as the database owner.
- `REQUIRE_AUTHENTICATED_PRINCIPAL=true`
- `APP_ENV=prod` (refuses to boot if the above flag is not set)

A verifying proxy in front of the API is mandatory in production: it must authenticate the caller, strip any client-supplied `X-Principal-Id` header, and set the verified principal id. See the Auth wiring row in [docs/stack/auth.md](docs/stack/auth.md) and the Production hardening section in [docs/reference/runtime.md](docs/reference/runtime.md).

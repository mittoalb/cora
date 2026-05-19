# Deployment

For operators bringing CORA up at a new facility (pilot target: APS 35-BM). Covers env-var posture, the bootstrap authz workflow, the first-boot Actor + Policy registration, and the recovery path when the seed gets corrupted.

## Env vars

The three load-bearing auth vars (full list in `.env.example`):

| Var | Default | When you set it |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql://cora:cora@localhost:5432/cora` | Always |
| `TRUST_POLICY_ID` | unset → `AllowAllAuthorize` | When you want real authz |
| `REQUIRE_AUTHENTICATED_PRINCIPAL` | `false` | Must be `true` whenever `TRUST_POLICY_ID` is set (the boot gate refuses otherwise — see below) |
| `ANTHROPIC_API_KEY` | unset → AI subscribers log-and-skip | When you want RunDebrief / CautionDrafter live |

### Startup boot gate

If you set `TRUST_POLICY_ID` without `REQUIRE_AUTHENTICATED_PRINCIPAL=true`, `create_app()` raises `RuntimeError` at boot. Rationale: without the header check, anyone can send `X-Principal-Id: 00000000-…0` and impersonate SYSTEM under the configured policy. Setting both together is the only safe combination; the seeded bootstrap policy permits SYSTEM to register Actors + define Policies, so anyone who can spoof the header gets standing admin.

Test env (`APP_ENV=test`) is exempt — legitimate test fixtures exercise the SYSTEM-fallback-under-real-policy scenario.

## Auth proxy contract

Production deployments MUST sit behind an auth proxy (nginx, Caddy, Cloud-IAP, AWS ALB, Globus Auth at APS) that:

1. Verifies the caller's identity via your facility's identity protocol (OIDC / Globus / SAML / mTLS).
2. **Strips any client-supplied `X-Principal-Id` header.** Critical — otherwise the boot gate's protection is bypassed by a header injection.
3. Sets `X-Principal-Id: <verified-caller-uuid>` based on the verified identity.

CORA reads `X-Principal-Id` directly from the request. Without the strip step, an unauthenticated client can claim to be anyone.

Phase C (edge-auth wiring) will land OIDC verification + JIT Actor provisioning inside CORA, reducing the proxy's contract to "verify identity" only. Until then, the proxy owns the identity → UUID mapping.

## First-boot workflow

A fresh deployment with `TRUST_POLICY_ID=00000000-0000-0000-0000-000000000001` (the seeded bootstrap policy) starts in a deliberate narrow-permissive state:

- The seed permits `SYSTEM_PRINCIPAL_ID` (the nil UUID `00000000-…0`) to call `DefinePolicy` and `RegisterActor`, both on the nil conduit (`UUID(int=0)`).
- That's it. Every other command Denies.

The operator's bootstrap path:

1. **Boot CORA** with both env vars set + the auth proxy in front.
2. **Configure the auth proxy to set `X-Principal-Id: 00000000-0000-0000-0000-000000000000`** for the operator's initial admin session. (Document this as a temporary "bootstrap session" in your proxy config — strip it after step 4.)
3. **Register your real admin Actor** via the API:

   ```
   POST /actors
   X-Principal-Id: 00000000-0000-0000-0000-000000000000
   Content-Type: application/json
   { "name": "<real admin name>" }
   ```

   Record the returned `actor_id` — this is your real admin's principal UUID.

4. **Define your real admin Policy** via the API:

   ```
   POST /policies
   X-Principal-Id: 00000000-0000-0000-0000-000000000000
   Content-Type: application/json
   {
     "name": "Real Admin Policy",
     "conduit_id": "00000000-0000-0000-0000-000000000000",
     "permitted_principals": ["<actor_id from step 3>"],
     "permitted_commands": ["DefinePolicy", "RegisterActor", "DefineZone", "DefineConduit", "..."]
   }
   ```

   Record the returned `policy_id`.

5. **Re-configure the auth proxy** to set `X-Principal-Id` to the real admin's UUID (from step 3) for the admin's verified identity. Remove the bootstrap-session SYSTEM override.

6. **Update `TRUST_POLICY_ID`** to the new `policy_id` from step 4 and restart.

The bootstrap seed stays on disk + in the event log forever — you can re-point at it during recovery scenarios.

## Recovery

### Bootstrap seed missing at startup

If the boot gate succeeds but `TRUST_POLICY_ID` points at `SYSTEM_BOOTSTRAP_POLICY_ID` and the seed stream is missing, `create_app()` raises `RuntimeError` at lifespan start with a runbook pointer. Cause: stale DB, restored backup that missed the seed, manual SQL that deleted it.

Recovery:

```
make migrate-apply
```

The seed migration (`infra/atlas/migrations/20260519000000_seed_bootstrap_policy.sql`) is idempotent (`ON CONFLICT DO NOTHING`) and safe to re-apply. After it lands, restart CORA.

### Real admin policy unreachable

If you've promoted a real admin Policy and lost the ability to call into it (compromised credentials, dropped key, etc.), re-point `TRUST_POLICY_ID` back to `SYSTEM_BOOTSTRAP_POLICY_ID` and run the first-boot workflow again with a new admin Actor. The old policy stays in the event log; the new one shadows it via `TRUST_POLICY_ID`.

### Diagnosing 403s in production

Logs to grep (structlog JSON):

| Symptom | Event name | Field to filter |
| --- | --- | --- |
| Every API call 403s | `trust_authorize.policy_missing` | `policy_id` |
| One principal can't call a command | `trust_authorize.deny` | `principal_id`, `command_name`, `reason` |
| One slice path 403s | `<slice_name>.denied` | `correlation_id` (joins to the underlying `trust_authorize` event) |

The `correlation_id` field is present on every `trust_authorize.*` event and every slice handler event, so a single Loki query `correlation_id="..."` traces the full request path.

For self-service "what CAN I do?" debugging, use:

```
GET /policies/{policy_id}/permissions?evaluated_principal_id=<me>&evaluated_conduit_id=00000000-0000-0000-0000-000000000000
```

This returns the sorted list of commands the named principal can run via the named conduit. The result is **not authoritative for authorization decisions** — it's a UX / debugging aid; only the PEP at each handler actually authorizes.

## Deferred (Phase B/C)

| Concern | Status | Trigger |
| --- | --- | --- |
| Container image + registry | Deferred | First non-local deployment |
| Runtime orchestrator (k8s / Cloud Run / ECS / bare VMs) | Deferred | First non-local deployment |
| Real OIDC / Globus / JWT verifier inside CORA | Phase C | Pilot deployment at APS |
| Per-surface conduit routing (HTTP / MCP / A2A) | Phase B | First mixed-surface deployment |
| `trust.check_others` permission separation | Watch item | When ABAC lands or first cross-tenant deploy |

See `memory/project_bootstrap_policy_design.md` + `memory/project_permissions_query_design.md` for design rationale + anti-hooks.

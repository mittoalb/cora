"""Actor display-surface helper + tombstone constant.

Per [[project_pii_vault]] strategic lock and
[[project_pii_vault_implementation_design]] Stage-1: human-facing
Actor PII lives in the mutable `actor_profile` side table. The
`ProfileStore` Protocol + `Profile` dataclass live in
`cora.infrastructure.ports.profile_store` because BOTH Access BC
and Agent BC consume the contract; the adapters live alongside
the other infrastructure adapters at
`cora.infrastructure.adapters.in_memory_profile_store` and
`cora.infrastructure.adapters.postgres_profile_store`. The Kernel exposes
the shared singleton via `deps.profile_store`.

This module hosts only what is genuinely Access-BC display
vocabulary: the tombstone literal and the read-helper that
returns it when a profile row is absent (erased or
never-registered). Adapters and Protocol intentionally stay
out of here so the BC ↔ infrastructure import direction stays
one-way.

## Display fallback

Post-erasure, the `actor_id` reference in events remains valid
(pseudonymised per EDPB 01/2025 Example 10). Read paths resolve
the display name via `load_actor_display_name`, which returns
the `DELETED_ACTOR_DISPLAY_NAME` literal when the profile row
is absent. The locale-neutral English literal is locked per the
existing [[project_deferred]] i18n entry (trigger: first
non-English facility deployment).
"""

from uuid import UUID

from cora.infrastructure.ports.profile_store import Profile, ProfileStore

DELETED_ACTOR_DISPLAY_NAME = "<deleted user>"


async def load_actor_display_name(profile_store: ProfileStore, actor_id: UUID) -> str:
    """Resolve the display name for an actor_id; tombstone fallback when absent.

    Read-path convention: any handler returning an Actor-display surface
    (REST DTO, MCP response, error message) calls this helper to get a
    UI-safe string. Returns `DELETED_ACTOR_DISPLAY_NAME` when the profile
    row is absent (erased OR never-registered).
    """
    profile = await profile_store.get(actor_id)
    return profile.name if profile else DELETED_ACTOR_DISPLAY_NAME


__all__ = [
    "DELETED_ACTOR_DISPLAY_NAME",
    "Profile",
    "ProfileStore",
    "load_actor_display_name",
]

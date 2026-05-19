"""Port `Protocol`s — contracts the application layer depends on.

Adapters implementing these ports live alongside (in `infrastructure/`) and are
wired into `Kernel` at startup. Domain and application code imports only
from `ports/`, never from adapter modules.
"""

from cora.infrastructure.ports.authorize import (
    Allow,
    AllowAllAuthorize,
    Authorize,
    AuthzResult,
    Deny,
)
from cora.infrastructure.ports.caution_lookup import (
    AlwaysQuietCautionLookup,
    CautionLookup,
    CautionReference,
)
from cora.infrastructure.ports.clearance_lookup import (
    AlwaysCoveredClearanceLookup,
    ClearanceLookup,
    ClearanceReference,
)
from cora.infrastructure.ports.clock import Clock, FrozenClock, SystemClock
from cora.infrastructure.ports.event_publisher import EventPublisher
from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    EventStore,
    NewEvent,
    StoredEvent,
)
from cora.infrastructure.ports.id_generator import (
    FixedIdGenerator,
    IdGenerator,
    UUIDv7Generator,
)
from cora.infrastructure.ports.idempotency import (
    CachedError,
    CachedHandlerError,
    CachedSuccess,
    Claimed,
    ClaimOutcome,
    HashConflict,
    IdempotencyClaimLostError,
    IdempotencyConflictError,
    IdempotencyStore,
    LockedRecent,
)
from cora.infrastructure.ports.llm import (
    CacheBreakpoint,
    CacheTTL,
    FakeLLMAdapter,
    FakeLLMExhaustedError,
    FakeLLMResponse,
    LLMAuthenticationError,
    LLMChatRequest,
    LLMContentBlock,
    LLMError,
    LLMInvalidRequestError,
    LLMPort,
    LLMRateLimitError,
    LLMResponse,
    LLMSchemaValidationError,
    LLMServerError,
    LLMSystemPrompt,
    LLMTimeoutError,
    LLMUsage,
    ModelRef,
)
from cora.infrastructure.ports.logbook_mirror import LogbookMirrorPort
from cora.infrastructure.ports.token_verifier import (
    IntrospectionUnavailableError,
    InvalidTokenError,
    PrincipalKind,
    TokenVerifier,
    VerifiedPrincipal,
)

__all__ = [
    "Allow",
    "AllowAllAuthorize",
    "AlwaysCoveredClearanceLookup",
    "AlwaysQuietCautionLookup",
    "Authorize",
    "AuthzResult",
    "CacheBreakpoint",
    "CacheTTL",
    "CachedError",
    "CachedHandlerError",
    "CachedSuccess",
    "CautionLookup",
    "CautionReference",
    "ClaimOutcome",
    "Claimed",
    "ClearanceLookup",
    "ClearanceReference",
    "Clock",
    "ConcurrencyError",
    "Deny",
    "EventPublisher",
    "EventStore",
    "FakeLLMAdapter",
    "FakeLLMExhaustedError",
    "FakeLLMResponse",
    "FixedIdGenerator",
    "FrozenClock",
    "HashConflict",
    "IdGenerator",
    "IdempotencyClaimLostError",
    "IdempotencyConflictError",
    "IdempotencyStore",
    "IntrospectionUnavailableError",
    "InvalidTokenError",
    "LLMAuthenticationError",
    "LLMChatRequest",
    "LLMContentBlock",
    "LLMError",
    "LLMInvalidRequestError",
    "LLMPort",
    "LLMRateLimitError",
    "LLMResponse",
    "LLMSchemaValidationError",
    "LLMServerError",
    "LLMSystemPrompt",
    "LLMTimeoutError",
    "LLMUsage",
    "LockedRecent",
    "LogbookMirrorPort",
    "ModelRef",
    "NewEvent",
    "PrincipalKind",
    "StoredEvent",
    "SystemClock",
    "TokenVerifier",
    "UUIDv7Generator",
    "VerifiedPrincipal",
]

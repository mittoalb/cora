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
    MinSeverity,
)
from cora.infrastructure.ports.clearance_lookup import (
    AlwaysCoveredClearanceLookup,
    ClearanceLookup,
    ClearanceReference,
)
from cora.infrastructure.ports.clock import Clock, FakeClock, SystemClock
from cora.infrastructure.ports.event_publisher import EventPublisher
from cora.infrastructure.ports.event_store import (
    ConcurrencyError,
    EventStore,
    NewEvent,
    StoredEvent,
    StreamAppend,
)
from cora.infrastructure.ports.id_generator import (
    FixedIdGenerator,
    FixedIdGeneratorExhaustedError,
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
    LLM,
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
    LLMRateLimitError,
    LLMResponse,
    LLMSchemaValidationError,
    LLMServerError,
    LLMSystemPrompt,
    LLMTimeoutError,
    LLMUsage,
    ModelRef,
)
from cora.infrastructure.ports.logbook_mirror import LogbookMirror
from cora.infrastructure.ports.profile_store import Profile, ProfileStore
from cora.infrastructure.ports.token_verifier import (
    IntrospectionUnavailableError,
    InvalidTokenError,
    PrincipalKind,
    TokenVerifier,
    VerifiedPrincipal,
)

__all__ = [
    "LLM",
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
    "FakeClock",
    "FakeLLMAdapter",
    "FakeLLMExhaustedError",
    "FakeLLMResponse",
    "FixedIdGenerator",
    "FixedIdGeneratorExhaustedError",
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
    "LLMRateLimitError",
    "LLMResponse",
    "LLMSchemaValidationError",
    "LLMServerError",
    "LLMSystemPrompt",
    "LLMTimeoutError",
    "LLMUsage",
    "LockedRecent",
    "LogbookMirror",
    "MinSeverity",
    "ModelRef",
    "NewEvent",
    "PrincipalKind",
    "Profile",
    "ProfileStore",
    "StoredEvent",
    "StreamAppend",
    "SystemClock",
    "TokenVerifier",
    "UUIDv7Generator",
    "VerifiedPrincipal",
]

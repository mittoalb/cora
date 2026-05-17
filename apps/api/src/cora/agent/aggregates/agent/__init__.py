"""Agent aggregate: state, status FSM, VOs, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.agent.features.<verb>_agent/` and import from here for state
and event types.

Public surface: status FSM + VOs + ModelRef + errors + events +
evolver + load_agent.

Phase 8f-a ships the foundation (define + version + deprecate + get);
no projection or list slice yet (deferred until per-kind active-agent
queries surface).
"""

from cora.agent.aggregates.agent.events import (
    AgentDefined,
    AgentDeprecated,
    AgentEvent,
    AgentVersioned,
    deserialize_model_ref,
    event_type_name,
    from_stored,
    serialize_model_ref,
    to_payload,
)
from cora.agent.aggregates.agent.evolver import evolve, fold
from cora.agent.aggregates.agent.read import load_agent
from cora.agent.aggregates.agent.state import (
    AGENT_CANONICAL_URI_MAX_LENGTH,
    AGENT_CAPABILITIES_MAX_COUNT,
    AGENT_CAPABILITY_MAX_LENGTH,
    AGENT_DEPRECATION_REASON_MAX_LENGTH,
    AGENT_DESCRIPTION_MAX_LENGTH,
    AGENT_KIND_MAX_LENGTH,
    AGENT_NAME_MAX_LENGTH,
    AGENT_VERSION_MAX_LENGTH,
    MODEL_REF_MODEL_MAX_LENGTH,
    MODEL_REF_PROVIDER_MAX_LENGTH,
    MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH,
    Agent,
    AgentAlreadyExistsError,
    AgentCannotDeprecateError,
    AgentCannotVersionError,
    AgentCanonicalURI,
    AgentCapability,
    AgentDeprecationReason,
    AgentDescription,
    AgentKind,
    AgentName,
    AgentNotFoundError,
    AgentStatus,
    AgentVersion,
    InvalidAgentCanonicalURIError,
    InvalidAgentCapabilitiesError,
    InvalidAgentCapabilityError,
    InvalidAgentDeprecationReasonError,
    InvalidAgentDescriptionError,
    InvalidAgentKindError,
    InvalidAgentNameError,
    InvalidAgentVersionError,
    InvalidModelRefError,
    ModelRef,
)

__all__ = [
    "AGENT_CANONICAL_URI_MAX_LENGTH",
    "AGENT_CAPABILITIES_MAX_COUNT",
    "AGENT_CAPABILITY_MAX_LENGTH",
    "AGENT_DEPRECATION_REASON_MAX_LENGTH",
    "AGENT_DESCRIPTION_MAX_LENGTH",
    "AGENT_KIND_MAX_LENGTH",
    "AGENT_NAME_MAX_LENGTH",
    "AGENT_VERSION_MAX_LENGTH",
    "MODEL_REF_MODEL_MAX_LENGTH",
    "MODEL_REF_PROVIDER_MAX_LENGTH",
    "MODEL_REF_SNAPSHOT_PIN_MAX_LENGTH",
    "Agent",
    "AgentAlreadyExistsError",
    "AgentCannotDeprecateError",
    "AgentCannotVersionError",
    "AgentCanonicalURI",
    "AgentCapability",
    "AgentDefined",
    "AgentDeprecated",
    "AgentDeprecationReason",
    "AgentDescription",
    "AgentEvent",
    "AgentKind",
    "AgentName",
    "AgentNotFoundError",
    "AgentStatus",
    "AgentVersion",
    "AgentVersioned",
    "InvalidAgentCanonicalURIError",
    "InvalidAgentCapabilitiesError",
    "InvalidAgentCapabilityError",
    "InvalidAgentDeprecationReasonError",
    "InvalidAgentDescriptionError",
    "InvalidAgentKindError",
    "InvalidAgentNameError",
    "InvalidAgentVersionError",
    "InvalidModelRefError",
    "ModelRef",
    "deserialize_model_ref",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_agent",
    "serialize_model_ref",
    "to_payload",
]

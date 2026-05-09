"""Commands for the Access BC.

Commands are intent-bearing requests addressed to the domain. They are
plain frozen dataclasses, named with PascalCase nouns matching the
verb-form decider that handles them (`RegisterActor` -> `register_actor`).

The command carries only what the caller controls. Server-side concerns
like the new aggregate id, the wall-clock timestamp, the correlation id,
and the command-instance id are injected by the application handler.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RegisterActor:
    """Register a new actor with the given display name."""

    name: str

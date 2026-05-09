"""Access bounded context.

Owns the identity and authentication concerns of CORA: who an actor is
and how they are recognized. Authorization (which actors can do what)
lives in the Trust BC; Access only answers "is this a known actor".

Phase 1 surface: a single `RegisterActor` command produces an
`ActorRegistered` event. The aggregate is `Actor`, keyed by a
server-generated UUIDv7.
"""

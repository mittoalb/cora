"""Cross-BC infrastructure adapters.

Production implementations of ports defined in `cora.infrastructure.ports`
that are consumed by multiple BCs (event store, idempotency, profile
store). Per [[adapter-naming-design]]: filename is
`snake_case(<Tech><Port>).py`, class is `<Tech><Port>` with no
`Adapter` suffix.
"""

"""Postgres tech primitives (connection pool).

Per [[adapter-naming-design]], Postgres adapters that implement
infrastructure ports live at `cora.infrastructure.adapters.postgres_*`.
This package keeps tech primitives that are NOT adapters (resources
shared by those adapters) such as the asyncpg connection pool.
"""

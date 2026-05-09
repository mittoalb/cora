"""Pytest configuration and shared fixtures.

Sets `APP_ENV=test` before any test imports so the FastAPI lifespan
selects the in-memory adapters by default. Integration tests that need
real Postgres bring their own fixtures and override the env there.
"""

import os

os.environ.setdefault("APP_ENV", "test")

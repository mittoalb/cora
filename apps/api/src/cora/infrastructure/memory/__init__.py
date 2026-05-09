"""In-memory adapters for the infrastructure ports.

Used for unit tests of application handlers and for any environment
(e.g. `app_env=test`) where a real database isn't available. Behavior
must match the Postgres adapters' contracts so that handler tests stay
honest about what production will do.
"""

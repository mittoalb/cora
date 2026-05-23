"""Shared MCP-tool contract-test helpers.

Two helpers, used by every `tests/contract/test_*_mcp_tool.py`:

  - `parse_sse_data(text)` — pulls the JSON object out of an SSE
    response body's `data:` line. FastMCP returns its responses as
    text/event-stream; the JSON-RPC envelope lives in a single
    `data:` line. We extract it and `json.loads` it.
  - `open_session(client)` — runs the MCP `initialize` →
    `notifications/initialized` handshake and returns the headers
    (including `mcp-session-id`) needed for subsequent `tools/list`
    and `tools/call` requests.

Extracted from the seven `test_*_mcp_tool.py` files that previously
each carried byte-identical copies. No leading underscore on the
function names so they're plain importable helpers (the file name
keeps the underscore to mark it as test-private).
"""

import json
from typing import Any

from fastapi.testclient import TestClient

HEADERS = {
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json",
}


def parse_sse_data(text: str) -> dict[str, Any]:
    """Pull the JSON object out of an SSE response (the `data:` line)."""
    for line in text.splitlines():
        if line.startswith("data:"):
            payload = line[len("data:") :].strip()
            return json.loads(payload)
    msg = f"No SSE data: line in response body: {text!r}"
    raise AssertionError(msg)


def open_session(
    client: TestClient,
    *,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Run initialize + notifications/initialized; return headers with session id.

    `extra_headers` (e.g. `{"Authorization": "Bearer ..."}`) ride on
    every request in the handshake AND are included in the returned
    headers so the caller's subsequent `tools/call` requests reuse
    them. Required under bearer-auth posture because even the
    `initialize` call flows through `BearerAuthMiddleware`.
    """
    extras = dict(extra_headers or {})
    init = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "contract-test", "version": "0.1"},
            },
        },
        headers={**HEADERS, **extras},
    )
    assert init.status_code == 200
    session_id = init.headers["mcp-session-id"]

    headers_with_session = {**HEADERS, **extras, "mcp-session-id": session_id}
    notif = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        headers=headers_with_session,
    )
    assert notif.status_code == 202
    return headers_with_session

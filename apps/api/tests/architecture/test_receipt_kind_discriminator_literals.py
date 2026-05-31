"""Pin ReceiptKind enum string values to the snake_case wire-spec set.

`ReceiptKind` discriminates the `SignatureEnvelope.receipts[].kind`
arms in the federation port contract. Each arm string is a wire-tier
literal aligned with the upstream standards' lowercase snake_case
conventions:

  - `scitt`        (SCITT, draft-ietf-scitt-architecture)
  - `rekor_sct`    (Sigstore Rekor signed certificate timestamp)
  - `ts_authority` (RFC 3161 timestamp authority token)

A future refactor that PascalCase-ifies these values (`Scitt`,
`RekorSct`, `TsAuthority`) would silently break wire compatibility
with peer adapters that read the discriminator string. This fitness
catches the drift at PR time.
"""

import pytest

from cora.federation.aggregates.permit.state import ReceiptKind


@pytest.mark.architecture
def test_receipt_kind_string_values_are_snake_case_wire_literals() -> None:
    assert {k.value for k in ReceiptKind} == {"scitt", "rekor_sct", "ts_authority"}

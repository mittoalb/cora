"""MCP tool for the ``record_attestation`` slice.

Surfaces the same handler the REST route uses, exposed as a Model
Context Protocol tool. The MCP tool flattens the nested ``evidence``
object into discrete arguments because FastMCP's tool-arg JSON Schema
is easier for LLM consumers to fill correctly when fields are flat;
the REST route preserves the nested shape for typed clients.
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal
from uuid import UUID

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from cora.data.aggregates.attestation import (
    ATTESTATION_ERROR_DETAIL_MAX_LENGTH,
    ATTESTATION_VERIFIER_KIND_MAX_LENGTH,
    AttestationKind,
    AttestationOutcome,
)
from cora.data.aggregates.dataset import DATASET_CHECKSUM_SHA256_HEX_LENGTH
from cora.data.features.record_attestation.command import RecordAttestation
from cora.data.features.record_attestation.handler import IdempotentHandler
from cora.infrastructure.mcp_principal import get_mcp_principal_id
from cora.infrastructure.observability import current_correlation_id
from cora.infrastructure.routing import get_mcp_surface_id


class RecordAttestationOutput(BaseModel):
    """Structured output of the ``record_attestation`` MCP tool."""

    attestation_id: UUID = Field(description="Identifier of the newly recorded Attestation.")


def register(mcp: FastMCP, *, get_handler: Callable[[], IdempotentHandler]) -> None:
    """Register the ``record_attestation`` tool on the given MCP server."""

    @mcp.tool(
        name="record_attestation",
        description=(
            "Record a new Attestation fact about a Dataset (always) and "
            "optionally a specific Distribution byte-copy. Today only "
            "kind='ChecksumVerified' is implemented; the other three kinds "
            "are reserved. Match/Mismatch outcomes require computed_checksum; "
            "Unreachable requires error_detail. The decider belt-and-braces "
            "compares evidence against the Distribution's canonical checksum "
            "to catch verifier-adapter bugs."
        ),
    )
    async def record_attestation_tool(  # pyright: ignore[reportUnusedFunction]
        ctx: Context[Any, Any, Any],
        dataset_id: Annotated[
            UUID,
            Field(description="Identifier of the Dataset the Attestation is about."),
        ],
        kind: Annotated[
            AttestationKind,
            Field(
                description=(
                    "What was attested. Closed enum: ChecksumVerified, "
                    "FormatValidated, ConformsToValidated, BitRotChecked."
                )
            ),
        ],
        outcome: Annotated[
            AttestationOutcome,
            Field(description=("Verifier outcome. Closed enum: Match, Mismatch, Unreachable.")),
        ],
        evidence_expected_checksum: Annotated[
            str,
            Field(
                min_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
                max_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
                pattern="^[0-9a-f]{64}$",
                description=(
                    "Canonical 64-char lowercase sha256 hex (the Distribution's expected value)."
                ),
            ),
        ],
        evidence_algorithm: Annotated[
            Literal["sha256"],
            Field(description="Checksum algorithm. Only 'sha256' supported today."),
        ],
        evidence_verifier_supply_id: Annotated[
            UUID,
            Field(
                description=(
                    "Identifies the Supply (or other adapter-resident endpoint) "
                    "the verifier walked. Forensic provenance."
                )
            ),
        ],
        evidence_verifier_kind: Annotated[
            str,
            Field(
                min_length=1,
                max_length=ATTESTATION_VERIFIER_KIND_MAX_LENGTH,
                description=("Short adapter name (e.g. 'HttpRangeChecksum'). Forensic provenance."),
            ),
        ],
        distribution_id: Annotated[
            UUID | None,
            Field(
                default=None,
                description=(
                    "Identifier of the bound Distribution byte-copy. Required "
                    "for byte-level kinds; null only for ConformsToValidated."
                ),
            ),
        ] = None,
        evidence_computed_checksum: Annotated[
            str | None,
            Field(
                default=None,
                min_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
                max_length=DATASET_CHECKSUM_SHA256_HEX_LENGTH,
                pattern="^[0-9a-f]{64}$",
                description=(
                    "Checksum the verifier computed. Required for "
                    "outcome=Match or outcome=Mismatch; null only for "
                    "outcome=Unreachable."
                ),
            ),
        ] = None,
        evidence_error_detail: Annotated[
            str | None,
            Field(
                default=None,
                min_length=1,
                max_length=ATTESTATION_ERROR_DETAIL_MAX_LENGTH,
                description=(
                    "Human-readable failure summary. Required for "
                    "outcome=Unreachable; null otherwise."
                ),
            ),
        ] = None,
    ) -> RecordAttestationOutput:
        handler = get_handler()
        attestation_id = await handler(
            RecordAttestation(
                dataset_id=dataset_id,
                distribution_id=distribution_id,
                kind=kind.value,
                outcome=outcome.value,
                evidence_expected_checksum=evidence_expected_checksum,
                evidence_computed_checksum=evidence_computed_checksum,
                evidence_algorithm=evidence_algorithm,
                evidence_verifier_supply_id=evidence_verifier_supply_id,
                evidence_verifier_kind=evidence_verifier_kind,
                evidence_error_detail=evidence_error_detail,
            ),
            principal_id=get_mcp_principal_id(ctx),
            correlation_id=current_correlation_id(),
            surface_id=get_mcp_surface_id(),
        )
        return RecordAttestationOutput(attestation_id=attestation_id)

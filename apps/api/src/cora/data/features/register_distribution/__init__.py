"""Vertical slice for the `RegisterDistribution` command.

Module-as-namespace surface mirrors `register_dataset`:

    from cora.data.features import register_distribution

    cmd = register_distribution.RegisterDistribution(
        dataset_id=dataset_id,
        supply_id=supply_id,
        uri="s3://aps-32id/runs/abc/recon.h5",
        checksum_algorithm="sha256",
        checksum_value="a" * 64,
        byte_size=1_073_741_824,
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://manual.nexusformat.org/"}),
        access_protocol="S3",
    )
    handler = register_distribution.bind(deps)
    distribution_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.data.features.register_distribution import tool
from cora.data.features.register_distribution.command import RegisterDistribution
from cora.data.features.register_distribution.context import (
    DistributionRegistrationContext,
)
from cora.data.features.register_distribution.decider import decide
from cora.data.features.register_distribution.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.data.features.register_distribution.route import router

__all__ = [
    "DistributionRegistrationContext",
    "Handler",
    "IdempotentHandler",
    "RegisterDistribution",
    "bind",
    "decide",
    "router",
    "tool",
]

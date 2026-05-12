"""Vertical slice for the `RegisterDataset` command.

Module-as-namespace surface:

    from cora.data.features import register_dataset

    cmd = register_dataset.RegisterDataset(
        name="32-ID FlyScan reconstruction",
        uri="s3://aps-32id/runs/abc/recon.h5",
        checksum_algorithm="sha256",
        checksum_value="a" * 64,
        byte_size=1_073_741_824,
        media_type="application/x-hdf5",
        conforms_to=frozenset({"https://manual.nexusformat.org/"}),
        producing_run_id=run_id,
        subject_id=subject_id,
        derived_from=frozenset({raw_dataset_id}),
    )
    handler = register_dataset.bind(deps)
    dataset_id = await handler(cmd, principal_id=..., correlation_id=...)
"""

from cora.data.features.register_dataset import tool
from cora.data.features.register_dataset.command import RegisterDataset
from cora.data.features.register_dataset.context import DatasetRegistrationContext
from cora.data.features.register_dataset.decider import decide
from cora.data.features.register_dataset.handler import (
    Handler,
    IdempotentHandler,
    bind,
)
from cora.data.features.register_dataset.route import router

__all__ = [
    "DatasetRegistrationContext",
    "Handler",
    "IdempotentHandler",
    "RegisterDataset",
    "bind",
    "decide",
    "router",
    "tool",
]

"""Dataset aggregate: state, status enum, errors, events, evolver, read repo.

Vertical slices that operate on this aggregate live under
`cora.data.features.<verb>_dataset/` and import from here for state
and event types. The `DatasetRegistrationContext` cross-aggregate
value object lives at `cora.data.features.register_dataset.context`
(slice-local; only register_dataset needs it today).
"""

from cora.data.aggregates.dataset.events import (
    DatasetEvent,
    DatasetRegistered,
    event_type_name,
    from_stored,
    to_payload,
)
from cora.data.aggregates.dataset.evolver import evolve, fold
from cora.data.aggregates.dataset.read import load_dataset
from cora.data.aggregates.dataset.state import (
    DATASET_CHECKSUM_ALGORITHM_SHA256,
    DATASET_CHECKSUM_SHA256_HEX_LENGTH,
    DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH,
    DATASET_CONFORMS_TO_MAX_ENTRIES,
    DATASET_DERIVED_FROM_MAX_ENTRIES,
    DATASET_MEDIA_TYPE_MAX_LENGTH,
    DATASET_NAME_MAX_LENGTH,
    DATASET_URI_MAX_LENGTH,
    Dataset,
    DatasetAlreadyExistsError,
    DatasetChecksum,
    DatasetFormat,
    DatasetName,
    DatasetNotFoundError,
    DatasetStatus,
    DatasetUri,
    DerivedFromDatasetsNotFoundError,
    InvalidDatasetByteSizeError,
    InvalidDatasetChecksumError,
    InvalidDatasetFormatError,
    InvalidDatasetNameError,
    InvalidDatasetUriError,
    InvalidDerivedFromError,
    LinkedSubjectNotFoundError,
    ProducingRunNotFoundError,
    validate_byte_size,
    validate_derived_from,
)

__all__ = [
    "DATASET_CHECKSUM_ALGORITHM_SHA256",
    "DATASET_CHECKSUM_SHA256_HEX_LENGTH",
    "DATASET_CONFORMS_TO_ENTRY_MAX_LENGTH",
    "DATASET_CONFORMS_TO_MAX_ENTRIES",
    "DATASET_DERIVED_FROM_MAX_ENTRIES",
    "DATASET_MEDIA_TYPE_MAX_LENGTH",
    "DATASET_NAME_MAX_LENGTH",
    "DATASET_URI_MAX_LENGTH",
    "Dataset",
    "DatasetAlreadyExistsError",
    "DatasetChecksum",
    "DatasetEvent",
    "DatasetFormat",
    "DatasetName",
    "DatasetNotFoundError",
    "DatasetRegistered",
    "DatasetStatus",
    "DatasetUri",
    "DerivedFromDatasetsNotFoundError",
    "InvalidDatasetByteSizeError",
    "InvalidDatasetChecksumError",
    "InvalidDatasetFormatError",
    "InvalidDatasetNameError",
    "InvalidDatasetUriError",
    "InvalidDerivedFromError",
    "LinkedSubjectNotFoundError",
    "ProducingRunNotFoundError",
    "event_type_name",
    "evolve",
    "fold",
    "from_stored",
    "load_dataset",
    "to_payload",
    "validate_byte_size",
    "validate_derived_from",
]

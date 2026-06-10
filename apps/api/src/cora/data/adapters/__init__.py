"""Data BC concrete port adapters.

Today ships one adapter:

  - ``HttpRangeChecksumAdapter`` implementing ``ChecksumVerifierPort``
    over HTTP / HTTPS via range-read in 1 MiB chunks.

Per [[project_adapter_naming_design]]: class name ``<Tech><Port>``;
module placement at ``cora.<bc>.adapters/`` for single-BC adapters,
or ``cora.<bc>.infrastructure.adapters/`` for cross-BC adapters.
``HttpRangeChecksumAdapter`` is Data-BC-only today.
"""

from cora.data.adapters.http_range_checksum import HttpRangeChecksumAdapter

__all__ = ["HttpRangeChecksumAdapter"]

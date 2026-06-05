"""Equipment BC adapters.

`StubDoiMinter` is the test-tier `DoiMinter` adapter per
[[project-asset-persistent-id-write-design]] (slice F.1): a real
adapter that returns inert deterministic values, distinct from a
None / disabled port. Mirrors `AllowAllAuthorize` and
`AlwaysCoveredClearanceLookup` test-bypass convention. The
production `DataCiteDoiMinter` adapter is deferred to slice F.2.
"""

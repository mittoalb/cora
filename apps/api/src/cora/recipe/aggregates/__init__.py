"""Aggregates owned by the Recipe BC.

Per the BC map's recipe ladder (ISA-88-aligned):
  - `Method` ≈ ISA-88 General Recipe (technique class, abstract over
    which Asset performs it).
  - `Practice` ≈ ISA-88 Site Recipe (facility-adapted Method, still
    abstract over Asset binding).
  - `Plan` ≈ ISA-88 Master / Control Recipe (concrete binding of
    Method to a specific Asset instance).
  - `Capability` — universal template that Methods and Procedures
    realize as executor-shaped variants.

`Run` (the actual execution) lives in the Run BC, not here.
"""

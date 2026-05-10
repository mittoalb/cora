"""Vertical slices owned by the Subject BC.

Slices ship per state transition:
  - 4a: register_subject
  - 4b: mount_subject
  - 4c: measure_subject, remove_subject
  - 4d: return_subject, store_subject, discard_subject (terminal)
  - 4e: get_subject (read side)
"""

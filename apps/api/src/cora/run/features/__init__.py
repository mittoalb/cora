"""Vertical slices owned by the Run BC.

Slices ship per state transition / aggregate operation:
  - 6f-1: start_run, get_run (the keystone scaffold)
  - 6f-2: complete_run, abort_run (terminal happy + emergency exit)
  - 6f-3: hold_run, resume_run, stop_run (pause cycle + controlled-exit terminal)
  - 6f-4 (deferred): truncate_run (partial-data terminal)
  - 6f-5 (deferred): more observation channels (motor positions; frame triggers post-DAQ)
"""

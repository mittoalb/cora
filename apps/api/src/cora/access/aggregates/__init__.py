"""Aggregates owned by the Access BC.

One subfolder per aggregate root, each holding the aggregate's intrinsic
shape: state + value objects + errors, the events the aggregate emits
(union alias), and the evolver that replays events back into state.
"""

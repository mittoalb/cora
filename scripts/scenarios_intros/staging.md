Pre-Run intake and clearance gates. Everything that must hold before `start_run` will succeed: a Subject registered against a proposal, mounted on the beamline apparatus, and an Active Clearance covering the work. Both the happy-path intake routines (`beamtime_intake`, `mount_sample`) and the gate-enforcement scenarios (`proposal_clearance` FSM walk, `run_start_gated_by_clearance`) sit here, because both shapes share the same purpose: gate the Run.

The cluster is bounded in scale: new safety form-types or new gate-rules add at most a scenario or two each.

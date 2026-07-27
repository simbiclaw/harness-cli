# Declared prototype deltas vs SPEC v1.2 (do not extend silently)

1. Planner = orchestrator main thread, not a separate subagent. Same "one
   agent, runs once" semantics; revisit at CLI migration.
2. contract.md -> contract.yaml (structured; gate needs machine-checkable fields).
3. Schema validation is field-presence/type checks in gate.py, not JSON Schema.
4. GM3 contradiction detection = any/none keyword intersection only.
5. GM4 executes only for `checkable: true` signals with keyword gate_patterns;
   substring matching stands in for the production matcher.
6. GM5 trigger extraction parses `trigger_id:/rule_id:` + `keywords:` lines;
   real companion formats may need a parser upgrade (flag, don't fudge).
7. Enforcement is prompt-discipline + gate script (D6 accepted risk). CI wiring
   of `gate.py rg` and epoch check is part of migration, not the prototype.
8. Evaluator's incremental re-review scope is enforced by prompt only.

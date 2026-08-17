# Dep-vet: pyyaml

Decision: APPROVED
Date: 2026-08-17

## Metadata
Ecosystem: pypi
First published: 2011-07-01 (release 3.10; earlier release keys lack upload records)
Latest version: 6.0.3
License: MIT
Source: https://github.com/yaml/pyyaml

## Checks
Age:        PASS (5526 days since first publish)
Downloads:  PASS (292,078,155/week)
Activity:   PASS (last commit 2026-06-17, 61 days ago)
License:    PASS (MIT)

## Rationale
PyYAML is used by the 9003 rubric-compiler runner and the compiler test
suites (`import yaml` in run_compile.py, befine.py, and tests) to read and
write the compiler inputs (specific-rubric.yaml / generic-skill.yaml /
align.md), the residue manifest, and the calibration manifest — YAML is the
INTENTS tree's on-disk format per `_meta/conventions.yaml`. The package has
been a transitive dependency in uv.lock all along; this record declares it
explicitly per the deps-and-secrets convention (the 9009 regrade flagged
the undeclared usage, dropping the io layer's boring-tech grade to D).
Alternatives considered: a hand-rolled YAML parser (rejected — the tree
format is the ecosystem standard and re-implementing it would create drift);
switching the tree to JSON (rejected — breaks INTENTS conventions.yaml and
the expertise-decision-log formats). PyYAML is the boring-tech choice:
20-year-old, MIT, 292M downloads/week, actively maintained.

Source: https://pypi.org/project/PyYAML/

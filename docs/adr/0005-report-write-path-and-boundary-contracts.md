# ADR-0005: The Consumer Contract (pointer)

**Status:** accepted (human-dictated 2026-09-16)

**Date:** 2026-09-16

## Decision

The consumer-side contract is **`INTENTS/PRODUCERS.md` §9** (epoch `631d16e`, stamped by
`9b6fcb5`), human-authorized 2026-09-16. That section is the **sole normative text** for:

- the consumer's single report write path and the narrowing of D15 to the referent rule
  (knowledge nodes stay zero-write);
- the upstream contract: criteria-shaped facets and producer output schemas;
- the downstream contract: sira-proxy renders the human-readable report from the tree.

This ADR deliberately restates none of it. One contract, one copy — duplication here
would be the two-copies-guaranteed-to-diverge failure the expertise-decision-log names.

## What changed on the harness-cli side (this repository only)

- `tests/test_no_write_path.py` — to be amended from "no `src/argus/` writes" to "no
  writes outside the report glob" (referent prohibition keeps its teeth), when the
  report schema lands.
- `_meta/ownership.yaml` (INTENTS) — needs a human-directed re-sync registering `argus`
  for the report glob **before any report lands** (zero-orphan CI); sequencing noted by
  doc2graph-0915 on 2026-09-16.
- D15 prose in CLAUDE.md's operating invariants and the plan-family citations — each
  superseded on that document's next executed touch; §9 governs meanwhile.

## Provenance

Human ruling 2026-09-16 ("no simbi at all"; scope = the pure derivation pipeline per
`docs/PRD/PMCA.txt`). Landed on this branch first; reaches `main` at the 9021 wrap-up
merge. Producers notified 2026-09-16 (audio2tree, doc2graph, soft-compiler sessions —
all three confirmed no write-footprint conflict; doc2graph's schema-landing pins are
recorded above).

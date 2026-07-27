# Artifact formats (prototype)

## proposal-r{n}.yaml / contract.yaml / compiled.yaml
```yaml
item_id: item_20
strategy: REFINE            # fix rounds only: REFINE | PIVOT (+ one-line justification)
contests: []                # optional; each: {finding, citation}
status: frozen              # contract.yaml only, added at freeze
epoch: <spec-epoch hash>
depends_on: [item_08]       # optional
trigger_keywords: [...]     # required if companion_docs present
companion_docs:             # copied from delegation packet
  - {path: companion/scripts.md, sha256: "...", role: trigger_source}
operationalization:
  signals:
    - id: S1
      description: "agent states the 7-day refund window before order confirmation"
      checkable: true
      gate_pattern: {any: ["7-day", "seven day refund"], none: ["no refund"]}
      audit_result: pass            # B-F: pass | split_needed | model_only
      grounding_refs: [rules_and_criteria]
      severity_key: refund_disclosure
    - id: S2
      description: "customer objection is acknowledged before rebuttal"
      checkable: false
      quarantine: S2                # mandatory when checkable: false
      audit_result: model_only
      grounding_refs: [best_practice_cookbook]
      severity_key: objection_handling
  applicability_gates:
    - {id: AG1, condition: {any: ["order"], none: ["complaint-only"]}}
verification_cases:
  - {id: V1, behavior: "transcript lacking any refund mention", expected: "S1 fails"}
coverage:
  clauses:
    - {clause: "must disclose refund window", signal_ids: [S1]}
known_defects: []           # spec-finding IDs riding on the frozen contract
```

## review-r{n}.md — YAML frontmatter + numbered findings body
```yaml
---
verdict: FIXES_NEEDED       # CONFIRMED | FIXES_NEEDED | AWAITING_STEERING
round: 1
fixes:
  - signal_id: S1
    field: gate_pattern
    issue: "misses zh-CN phrasing of the window"
    fix_direction: "add localized keyword variants from packet extraction"
    citation: "align.md - 'coverage must span deployed locales'"
---
```

## spec-findings.md entry (append-only)
```
## SF-<run>-<seq>
author: generator|evaluator|planner
target: align.md
clause: "<verbatim quote>" (location: section/line)
class: gap|ambiguity|contradiction|untestable   # metadata; nothing gates on it
evidence: item_20 round 2 - <what happened>
evolution_direction: "any fix must <property>"  # PROSE ONLY - no candidate spec text (D2/C2)
```

## residue-manifest.yaml
```yaml
entries:
  - item: item_20
    lost: "tone-of-acknowledgment nuance"
    where: "S2 quarantined to S2-stage model proposal"
    class: judgment_not_operationalizable
```

# M6a — Compiler agent skill: GAN loop over the deterministic core (9003)

### [plan-confirmed] — Runner rewired onto the M1-M5 core (round-3 decision 1)

Emitted nodes ARE the pure-core derivation: decompose_signals → classify_gap
→ assign_facets → declare_residue → seed_agreement_gate → set_deduction_weight
→ bind_item_to_dimension → compile_applicability_gate → extract_values →
synthesize_hard_fail; corroborators via classify_corroborators. The template
path is gone (gap_type_for / mock_evaluate deleted). --evaluator mock runs the
same real path (kept for backward compat).

### [plan-confirmed] — Evaluator wires validate_node + all context checks (M1 F9 closure)

check_manifest_present (provisional manifest assembled after generate),
check_calibration_coverage, check_no_forced_mapping, check_depends_on,
check_edited_consistency, check_exclusion_set_adversarial — all invoked with
the run's context. AUTH-5/AUTH-10 can never fire on runner output by
construction (manifest always assembled; unmapped items become gap rows) —
by-construction safety, not dead code.

### [discovery] — Three adversarial rounds converged on CLI robustness

Round 1: mock bypassed the M5 gate (NameError), garbage inputs tracebacked.
Round 2: JSON layer escaped the boundary (JSONDecodeError/AttributeError),
standalone generate/evaluate ungated, REPO_ROOT off-by-one (parents[3] =
.claude/), --fix silently no-opped on unknown ids, standalone generate
duplicated gap rows, evaluate-on-empty falsely CONFIRMED. All closed.

### [discovery] — D8 node_id convention note

check_edited_consistency compares depends_on refs ("20") against sibling
node_ids ("item-20"); the runner projects the item-id convention onto the
sibling context. A future core note if the D8 convention is intended
differently.

### [discovery] — Fix rounds are by-construction unreachable from core output

The M1-M5 chain never produces validator-failing content (unmatched standards
degrade to model_based; refs always resolve). The ≤3 fix rounds become
reachable when the real GAN Evaluator (model-judged steps per SKILL.md)
runs — the discipline is wired, the trigger awaits the agentic path.

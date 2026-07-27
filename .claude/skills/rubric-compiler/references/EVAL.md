# Hard-test protocol (run BEFORE CLI migration; gate for Option A)

Fixtures: build a `testdata/` specs dir with ~6 items: 2 clean simple, 1 with
companion docs, 1 with a dependency chain, 1 seeded with spec defects, 1
genuinely contested (no right operationalization).

T1 Gate determinism: run `gate.py item` 3x on identical artifacts -> identical
   reports (byte-equal minus timestamps). Any diff = gate bug, highest severity.
T2 Seeded-defect catch rate: plant one violation per GM check (bare adjective,
   checkable-without-pattern, any/none overlap, exclusion suppressing positive
   frame, missing trigger keyword, uncovered clause) -> gate must catch 6/6,
   with correct BLOCK/WARN class.
T3 Pre-compile halts: SHA mismatch, conflicting trigger IDs, dependency cycle
   -> all three halt before dispatch with steering entries quoting sources.
T4 Evaluator leniency probe: hand the evaluator a proposal with a real but
   subtle hidden model dependency (checkable: true that needs judgment).
   Pass = FIXES_NEEDED citing it. Run 5x; count misses. This is the C2-adjacent
   soft spot - a lenient evaluator makes G5 decorative.
T5 Goal-pressure probe: contested item at round 3. Pass = AWAITING_STEERING
   with digest; fail = squeezed CONFIRMED. Verify orchestrator reports steering
   items as success, not as unfinished work.
T6 Targeted-fix regression: fix round touching S1 silently breaks S3's
   coverage -> full gate re-run must catch it even though evaluator only
   re-reviewed S1.
T7 Loop metrics to record per run: rounds/item, steering rate, GM WARN counts,
   contest rate, spec-findings count. These are the baseline for the CLI's
   regression eval.
T8 Epoch: touch align.md one char -> epoch differs; rerun compiles all items.

Exit criteria for migration: T1-T3, T6, T8 at 100%; T4 >= 4/5; T5 pass;
metrics recorded.

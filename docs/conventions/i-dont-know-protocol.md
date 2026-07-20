# The "I Don't Know" Protocol

When Claude Code makes a decision under uncertainty, it cites evidence or flags the uncertainty explicitly. Generic confidence is a bug.

## Every Decision Log entry has a Rationale

The Rationale must be one of three shapes.

### Cited

```
Rationale: <one-sentence explanation>.
Source: <URL or path:lineRange>
```

Example:

```
Rationale: chose UUID v7 because it preserves time-ordering for index efficiency.
Source: https://datatracker.ietf.org/doc/html/rfc9562
```

### Empirical

```
Rationale: <one-sentence explanation>.
Experiment: docs/experiments/<NNNN>-<name>/
```

The experiment directory contains a runnable script and the captured output that demonstrates the property the decision rests on. Experiments are written as small, self-contained Python scripts (`run.py`) plus an `output.txt` (or `output.json`) with the captured result. Anyone reading the Decision Log can re-run the experiment and verify the claim.

Example:

```
Rationale: chose orjson over stdlib json for serialization because measured
throughput on a 10 MB document was 6x faster.
Experiment: docs/experiments/0007-json-serialization-throughput/
```

### Marked-as-guess

```
Rationale: <one-sentence>. Confidence: low.
Revisit: by milestone-NNN | by YYYY-MM-DD
```

This shape creates a corresponding entry in the ExecPlan's Surprises & Discoveries section with the same Revisit deadline, so the doc-gardener can surface it when the deadline passes.

Example:

```
Rationale: defaulted to TOML for the config format because it ships with stdlib
in Python 3.11+. Confidence: low.
Revisit: by 2026-08-01
```

## Forbidden phrases

The following phrases are banned in any Decision Log entry, regardless of context. The structural test `test_no_forbidden_phrases.py` enforces this:

- "standard approach"
- "best practice"
- "industry standard"
- "commonly used"
- "widely accepted"
- "the go-to"
- "people generally"
- "everyone knows"
- "canonical"
- "what most projects do"

These phrases are tells for unsupported confidence. If you would write one of them, you are guessing — use the Marked-as-guess shape instead.

## Wikipedia is not evidence

Citations must be either:

- **Primary sources**: the project's own docs, source code on GitHub, RFCs, language standards, PEPs.
- **In-repo experiments**: scripts you ran with captured output.

Aggregator articles, ranking lists ("top 10 X"), tutorial sites (geeksforgeeks, freecodecamp, dev.to surveys), and Wikipedia survey articles do not count as evidence for an engineering decision. The structural test accepts any URL today, but the doc-gardener flags suspicious citation domains for review.

## When the right move is to write an experiment

If you find yourself wanting to write a Marked-as-guess Rationale because you genuinely don't know, the correct move *during* execution is to spend 15 minutes writing an experiment. Drop it in `docs/experiments/<NNNN>-<name>/`, run it, capture output, and cite the experiment. This is faster than the Marked-as-guess approach over any non-trivial timeline because the Revisit deadline will eventually surface and you'll be writing the experiment then anyway.

Marked-as-guess is for cases where the cost of an experiment exceeds the cost of being wrong (e.g. choices that are easy to revisit later because they are well-isolated).

Last reviewed: 2026-07-20

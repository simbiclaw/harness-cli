# 9029 — The Surface: Proposer Demotion, CLI, Config, Record

## 1. Purpose

Everything an operator touches, and the one proposer-side change the architecture review left
standing: the 9020 proposer demoted from a verdict path to an observable drift probe, and the
command, configuration and record surfaces the tool presents. Each of the three surfaces is a public
contract, which is why they are together and why each is gated.

## 2. Big Picture

**The demotion is not a deletion.** The proposer's continuous self-report never shipped and never
will (D7/D8); what remains useful is the *divergence* between what the model believed and what the
pure stages derived — a calibration signal. M20 makes it observable and makes its inputs comparable
first: the module keys by its own dimension strings on a 0–1 scale while the derived side keys by
the rubric categories on 0–100, and it silently skips dimensions absent on either side. Unifying
keys and units comes before anything reads it, or the probe reports "flat" forever.

**Three Tier C surfaces, each individually gated.** M22 lands B's run modes under this repository's
entry point (Q17 — the only steering question in this family still open, deadline 2026-09-30),
typed configuration in `src/argus/config/**` (Q11, resolved), and the sidecar run manifest (Q19,
resolved). The binding constraint across all three: **no value that alters a verdict may live as a
hardcoded constant** — which is why the dimension weights had to be compiled (9026) rather than
configured.

**Depends on:** 9027 and 9028 (the stages whose results the surface presents).

**File Scope:**
- `docs/exec-plans/active/9029-surface.md` (this plan)
- `src/argus/core/divergence.py` (modify — keys, units, the disjoint-key guard)
- `src/argus/cli/main.py` (modify)
- `src/argus/config/**` (new — sensitive path, gated on Q11)
- `tests/test_divergence.py`
- `tests/test_cli.py` (new)

## 3. Milestones

### M20 — Demote the 9020 proposer to a drift probe, safely

`core/divergence.py:52-56` silently skips dimensions absent on either side. The proposer keys by
its own dimension strings on a `[0,k-1]` scale; the derived side keys by the five rubric categories
on 0–100. Unify keys and units first, or the probe reports "flat" forever.

`Notes:` If the proposer runs on MLX rather than llama.cpp (Q21), the cache rewind is **not**
`model.n_tokens = prefix_len` and **not** `trim_prompt_cache`, which is unavailable on both pinned
model families. It is a per-cache-type deep-copy snapshot and restore covering **both** `state` and
`meta_state` — `RotatingKVCache` keeps `offset` and `_idx` in `meta_state`, so restoring `state`
alone rewinds to the wrong position. A snapshot taken by reference is silently wrong rather than
broken: mlx mutates cache buffers in place and its arrays have no `.copy()`, and a measured
reference "snapshot" replayed to `max|Δlogit| = 6.06`, i.e. a different `proposed_score` with no
error raised. Measured in issue #15.

`Acceptance Test:` `tests/test_divergence.py::test_disjoint_keys_raise` — mismatched vocabularies
raise rather than returning an empty dict. `::test_units_are_comparable`. If Q21 brings an MLX
Provider into scope, add `::test_cache_rewind_is_bit_exact` — replaying a suffix after a rewind
gives `max|Δlogit| == 0.0`, with a reference-snapshot red case.


**Contract.**
- *Deliverable:* The existing proposer repurposed as an observable drift probe.
- *Binding constraint:* I7 and D7 — a proposed score is never a verdict. D12 — resample variance never touches routing.
- *Acceptance property:* The probe fails loudly on incomparable inputs rather than reporting stability, and divergence is logged rather than routed.
- *Known evidence (advisory):* Key vocabularies and score units differ between the two sides. On MLX the cache rewind is not the llama.cpp primitive and the obvious implementation is silently wrong — see the milestone notes.


### M22 — Surface: CLI, config, record format

B's three run modes under this repository's entry point; typed configuration in `config/`; the
sidecar run manifest. Each is Tier C and individually gated.

`Acceptance Test:` `tests/test_cli.py::test_eval_subcommand_exits_zero` — invoked as a subprocess
against a real transcript. `::test_json_mode_is_machine_readable`.

**Contract.**
- *Deliverable:* The command, configuration and record surfaces.
- *Binding constraint:* Each is a public contract and Tier C. No value that alters a verdict may live as a hardcoded constant.
- *Acceptance property:* The command runs against a real transcript and exits non-zero on failure; every verdict-affecting value has a declared home.
- *Known evidence (advisory):* B's key set contains dead and silently duplicated values, and at least two floors have no declared number anywhere. Discover the real set by building it.


## 4. Progress

- [ ] M20: Demote the 9020 proposer to a drift probe, safely  (created 2026-09-12)
- [ ] M22: Surface — CLI, config, record format  (created 2026-09-12)

## 5. Decision Log

### Decision: The divergence probe is observable, never routed (2026-09-14, inherited)

**Rationale:** `Source:` I7 and D7 — a proposed score is never a verdict; D12 — resample variance
never touches routing. The probe fails loudly on incomparable inputs rather than reporting
stability, and divergence is logged rather than routed. The archived plan's entry records how the
D20 × I8 tension was resolved toward the stricter reading.

**Confidence:** medium in the archive's words; the direction (alert, never demote) is the strict one.

### Decision: The surface's values are discovered, not guessed (2026-09-12, inherited)

**Rationale:** `Source:` M22's Contract — B's key set contains dead and silently duplicated values,
and at least two floors have no declared number anywhere. The contents are discovered by building
the surface under the binding constraint that no verdict-altering value is a hardcoded constant.

**Confidence:** high on the constraint; the key list is the milestone's discovery.

## 6. Surprises & Discoveries

**On the MLX path the cache rewind is silently wrong if implemented naively (2026-09-12, inherited).**
If the proposer runs on MLX rather than llama.cpp, the rewind is **not** `model.n_tokens = prefix_len`
and not `trim_prompt_cache`: it is a per-cache-type deep-copy snapshot covering both `state` and
`meta_state` — `RotatingKVCache` keeps `offset` and `_idx` in `meta_state`, so restoring `state`
alone rewinds to the wrong position. A snapshot taken by reference is silently wrong rather than
broken: measured, a reference "snapshot" replayed to `max|Δlogit| = 6.06`, i.e. a different
`proposed_score` with no error raised. Recorded because the obvious implementation is the wrong one.

**The `LogitModel` protocol is not portable (2026-09-13, inherited).** Its docstring promises five
members; `local_proposer.py` calls a sixth. Latent while one implementation exists, and it blocks any
adapter.

## 7. Awaiting Steering

**Q17: Adopt B's CLI surface?** Deadline 2026-09-30, **unresolved — the only open steering question
in this family.** B offers three run modes; this repository has a `version` stub. Tier C — CLI
surface and stdout format, and `src/argus/cli/main.py` is a sensitive path. Default if not decided:
adopt the three modes, drop the index-building mode whose output nothing reads, and add a JSON mode
as the machine contract.

**Q11 (config surface) and Q19 (record format)** are resolved — see the archived plan.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*

# M5 round-4 implementation brief — local continuation, 2026-09-14

For the dispatched implementer (subagent A). The handoff
(`HANDOFF-2026-09-14.md`) and `M5.md` carry the history; this file adds the
design decisions for the four unattempted defects and the mechanical rules the
rewrite must follow. Read all three before touching anything.

## State at handoff (verified locally, 2026-09-14)

- Branch `claude/9021-m5-handoff-local`, commit `2e96925`: round-4 builder
  landed unmodified from `wip/m5-round4-builder@1852aaa`; fixture regenerated
  from a **local** upstream checkout (`/Users/prometheus/workspace/simbi`,
  HEAD = `0c2cccd...`, provenance checks passed). Suite: **2 failed,
  22 passed** — the handoff's exact prediction.
- Run the suite with:
  `PYTHONPATH=src /Users/prometheus/workspace/harness-cli/.venv/bin/python -m pytest tests/test_schemas.py -q`
  (system python3.14 lacks pydantic; the venv has pydantic 2.13.4 + pytest).
- Re-run the builder with:
  `PYTHONPATH=src .venv/bin/python scripts/build_schema_snapshot.py --upstream /Users/prometheus/workspace/simbi`

## The encoder duplication rule (do not break it)

`scripts/build_schema_snapshot.py` and `tests/test_schemas.py` deliberately
carry **mirror implementations** of the same encodings (`default_key`,
annotation normalization, field/model/enum facts). Merging them into one
import would make a regression in the encoder move both sides together and
cancel out — the exact failure M5.md's third deviation documents. The named
regression test (`test_a_generated_value_is_guarded_by_its_freshness_not_its_type`)
pins the encoding precisely because of this. Keep the duplication; extend the
regression test to pin every new key form.

## Design decisions for defects 8–11 (Group B)

### Defect 8 — empty-container freshness gap → identity probe

Current `default_key` returns `repr(produced)` for empty results before any
sampling, so `default_factory=lambda: _SHARED_LIST` (a module-level list) and
`default_factory=list` both encode to `[]` — and two `Session()` instances
share one mutable `metadata`/`turns` object.

Fix, in **both** the builder's `default_key` and the test's `_default_key`:
for an empty **mutable** container (`type(produced) in (list, dict, set)` —
do NOT extend to tuple/frozenset/str: those are immutable and CPython legally
interns them, e.g. `lambda: ()` returns the same object every call; sharing an
immutable is harmless), call the factory two more times and test identity:
any two results `is`-identical → `<factory:{type}:shared-empty>`, else
`<factory:{type}:fresh-empty>`. Value-equality cannot see shared mutability;
identity can. Runs regardless of falsiness only for the mutable-container
branch; everything else keeps the existing paths.

### Defect 9 — weak entropy sampler → tiered classification with a documented floor

Three draws classify `uuid4()[:1]` (16 distinct values over 2000 calls) as
"fresh". Fix: draw **N=24** times; 1 distinct value →
`<factory:{type}:constant>`; N distinct → `<factory:{type}:fresh>`; anything
between → `<factory:{type}:weak>`.

Say what the check is, honestly, in a comment: this is a **statistical
proxy with a documented floor**, not an entropy guarantee. 24 all-distinct
draws over a 16⁸ space collides with p ≈ 7×10⁻⁸; over a 16-value alphabet it
collides with certainty. That is the discrimination the contract needs
(upstream's `session_id` is uuid4-hex; the mutation to catch is a low-entropy
substitute). Keep the exact strings `<factory:str:fresh>` and
`<factory:str:constant>` — the existing regression test and the regenerated
snapshot pin them; only the middle tier is new.

### Defect 10 — extra classes invisible → exact set equality, counts retired

`compare_to_snapshot` iterates the snapshot and checks the port has everything
upstream has; a `class SmuggledScore(BaseModel): proposed_score: float = 0.0`
in the port passes green, and `proposed_score` is precisely the name I5/I7
keep out of this contract.

Fix, three assertions:
1. Port snapshot keys (models ∪ enums, via the mirrored `snapshot_module`)
   must **exactly equal** SNAP's keys — `==`, not ⊆. Missing and extra both
   fail, named.
2. SNAP's keys must equal `set(SNAP["declared_classes"])` — the builder's
   AST parse of the upstream source is an independent mechanism from the
   import; if they disagree, the snapshot itself is untrustworthy.
3. **Retire** the `len(SNAP["models"]) == 16` / `== 10` count assertions in
   `test_no_upstream_model_or_enum_is_missing` — a count is the hand-written
   table failure shape relocated from names to numbers. The set equality
   replaces them.

### Defect 11 — enum aliases skipped → `__members__`

`{m.name: m.value for m in obj}` skips aliased members. Builder
`enum_facts` and the test mirror both switch to
`[[name, member.value] for name, member in member_type.__members__.items()]`
— ordered, alias-inclusive. (`__members__` preserves declaration order with
aliases adjacent to their canonical member.)

## The comparison rewrite

Replace the hand-grown `compare_to_snapshot` walk with: build a port document
via the mirrored `snapshot_module(p)`, then a generic
`diff_documents(upstream, port)` that mechanically compares **every recorded
fact** and returns one line per difference:

- models: missing / extra (both directions) / field order / `config` dict /
  `decorators` buckets / per-field all nine facts (required, default,
  annotation, alias, validation_alias, serialization_alias, constraints,
  frozen, exclude)
- enums: missing / extra / `bases` / ordered `members`

No per-fact hand assertions anywhere — a fact is compared because it is
recorded, not because someone remembered it.

**Gotcha:** the builder's `snapshot_module(module, owned)` filters classes by
`obj.__module__ in owned`. For the live port pass `owned={"argus.types.pipeline"}`.
For the mutation stand-ins in `test_the_checks_can_fail` — `ns.__dict__.update(vars(p))`
keeps original classes' `__module__` at `argus.types.pipeline` while
replacement classes are defined in the test module — pass
`owned={"argus.types.pipeline", <test module name>}` or the stand-in snapshots
empty and every mutation "passes" vacuously. This is the same
baseline-first trap the existing test already guards; keep that guard.

## test_the_checks_can_fail — extend the live mutation battery

Keep the existing six plants; add one per new fact class so the suite
demonstrates each fires: alias added, `ge=` constraint added,
`model_config` `extra="forbid"`, `@field_validator` zeroing `score`,
`@model_validator` clearing `evidence`, enum base `(str, Enum)` → `(Enum)`,
enum members reordered, enum alias added, `Session.metadata` factory
returning a shared module-level dict (defect 8), `session_id` factory
`uuid4()[:1]` (defect 9 — must encode `weak`, not `fresh`), and a smuggled
extra model (defect 10).

## The mutation sweep (step 3 of the handoff's "done")

`scripts/mutate_m5_contract.py`: applies each of the 19 known defects as a
one-at-a-time textual mutation to `src/argus/types/pipeline.py` (or the
fixture, where noted), runs the suite, restores, and prints a table.
Backup/restore must be exception-safe (the port file is untouchable
territory; a crashed sweep must not leave a mutated tree). Every row must
come out **red**; any survivor means the repair is incomplete and is a
finding, not a footnote.

The 19, enumerated from the handoff: (1) field alias, (2) `FieldInfo`
constraint, (3) `extra="forbid"`, (4) `frozen=True`, (5) `str_to_lower`,
(6) `str_strip_whitespace`, (7) score-zeroing `@field_validator`,
(8) evidence-clearing `@model_validator`, (9) enum base non-`str`,
(10) enum reorder, (11) provenance — digest hand-edit of the fixture
(fixture mutation, restored), (12) shared-empty factory (defect 8),
(13) weak-entropy factory (defect 9), (14) smuggled extra class (defect 10),
(15) enum alias added (defect 11), (16) deleted field, (17) changed default
(`RubricItem.weight` 1.0→2.0), (18) widened annotation (`Literal` → `str`),
(19) relaxed requirement (`Atom.source_turn_ids` required→optional).

Numbering in the committed table should cite the handoff's grouping so the
two documents cross-reference.

## Constraints (unchanged from the handoff)

- Do not touch `src/argus/types/pipeline.py` (outside the sweep's temporary,
  always-restored mutations), `CLAUDE.md`, `pyproject.toml`, `.importlinter`,
  anything under `.claude/`.
- `simbiclaw/sim` (local: `/Users/prometheus/workspace/simbi`) is read-only.
- Do not commit — the orchestrator reviews, runs the sweep, and commits.
- End state: suite green (unmutated port, regenerated fixture), every new
  fact class demonstrated to fire, sweep table all-red.

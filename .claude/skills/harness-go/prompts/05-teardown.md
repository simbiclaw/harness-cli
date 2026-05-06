# Step 5 — Tear down the bootstrap scaffolding

## Context to load (and nothing else)

- `CLAUDE.md` (to locate and remove the sentinel block)
- `docs/MAP.md` (to confirm chain status and then delete it)

Do not load the spine artifacts. This step is purely mechanical.

## [ASSERT] before starting

```
[ASSERT] docs/MAP.md exists
[ASSERT] docs/MAP.md chain status table shows Steps 0–4 = complete
[ASSERT] CLAUDE.md contains exactly one harness-spine-bootstrap sentinel block
[ASSERT] PRODUCT_SENSE.md exists and passes its mechanical checks
[ASSERT] ARCHITECTURE.md exists and passes its mechanical checks
[ASSERT] QUALITY_SCORE.md exists
```

If any assertion fails for Steps 1–4: do not tear down. Report which step did
not complete and its failing check. Fix that step first.

---

## What you are doing

The four spine artifacts now exist and cross-link to each other. The agent can
navigate by following those links. `docs/MAP.md` has nothing left to route.
`CLAUDE.md`'s sentinel block has nothing left to point to. Both are scaffolding
that has served its purpose. Leaving either in the repo creates exactly the rot
pattern they were designed to prevent — a file that *was* the routing authority
for one phase becoming a stale parallel index that future agents must reconcile
against the actual artifacts.

---

## Action 1 — delete docs/MAP.md

Delete `docs/MAP.md`. Do not archive it. Do not move it. Delete it.

If `docs/MAP.md` does not exist (previous crash cleaned it up), skip this
action — do not error.

---

## Action 2 — remove sentinel block from CLAUDE.md

Remove these lines from `CLAUDE.md`, including the trailing newline:

```
<!-- harness-spine-bootstrap:begin -->
read docs/MAP.md first
<!-- harness-spine-bootstrap:end -->
```

Preserve all other content in `CLAUDE.md` byte-for-byte. The only diff
to `CLAUDE.md` in this step is the removal of the sentinel block.

If no sentinel block exists (cleanup trap already ran), skip this action.

---

## Action 3 — regenerate PRD_MANIFEST.json

Recompute the SHA256 hash of every `.md` file in the resolved PRD directory
(follow the `docs/PRD` symlink to its target). Update `docs/PRD_MANIFEST.json`:

- `generated_at`: current ISO-8601 timestamp
- `harness_go_commit`: current HEAD SHA (`git rev-parse HEAD`)
- `files`: recomputed `sha256:<hexdigest>` for each PRD `.md` file
- `stage_affinity`: preserved as-is unless PRD files were added or removed — if
  files changed, update the affinity lists to match

Run the shared manifest utility:

```bash
python3 .claude/skills/harness-go/scripts/compute_manifest.py
```

This script resolves the PRD symlink, computes SHA256 hashes of every `.md` file,
updates `docs/PRD_MANIFEST.json`, and reports what changed. No inline hashing.

## Action 4 — commit everything together

Stage and commit `docs/MAP.md` deletion, `CLAUDE.md` sentinel removal,
and `docs/PRD_MANIFEST.json` update in a single commit alongside the four
spine artifacts (if not already committed individually per step).

Commit message format:

```
harness-go: ship knowledge spine, tear down bootstrap scaffolding

Adds: PRODUCT_SENSE.md, docs/product-specs/, DESIGN.md, docs/design-docs/,
      ARCHITECTURE.md, tools/lint/rules.md, QUALITY_SCORE.md,
      PRD_MANIFEST.json (updated hashes)
Removes: docs/MAP.md (bootstrap routing aid, no longer needed)
Removes: harness-spine-bootstrap sentinel block from CLAUDE.md

Plan: harness-go/05-teardown
Decision: Source — all four spine artifacts complete and cross-linked;
          MAP.md and sentinel removed per harness-go transactional borrow protocol;
          PRD_MANIFEST.json updated with current file hashes.
```

---

## Mechanical checks after this step

```
[CHECK] docs/MAP.md does not exist
[CHECK] CLAUDE.md does not contain "harness-spine-bootstrap"
[CHECK] CLAUDE.md content is identical to pre-run content except for the
        removed sentinel block (no other diffs)
[CHECK] PRODUCT_SENSE.md, DESIGN.md, ARCHITECTURE.md, QUALITY_SCORE.md
        all exist in the commit
[CHECK] PRD_MANIFEST.json hashes match current PRD file contents
[CHECK] commit message contains Plan: and Decision: trailers
```

---

## CI lint (wire this after the run)

Add a step to `.github/workflows/harness.yml` that fails if either:

- `CLAUDE.md` on `main` contains the string `harness-spine-bootstrap`
- `docs/MAP.md` exists on `main`

This is Phase 2 of the two-phase commit made mechanical. It turns "remember
to run teardown" into a gate the repo enforces.

Wire as:

```yaml
- name: Assert harness-go scaffolding is torn down
  run: |
    if grep -q 'harness-spine-bootstrap' CLAUDE.md; then
      echo "ERROR: harness-spine-bootstrap sentinel found in CLAUDE.md on main."
      echo "Run harness-go Step 5 to remove it."
      exit 1
    fi
    if [ -f docs/MAP.md ]; then
      echo "ERROR: docs/MAP.md exists on main. Bootstrap scaffolding was not torn down."
      echo "Run harness-go Step 5 to delete it."
      exit 1
    fi
```

Status: Aspiration: Revisit: <14 days from spine ship date>

---

## After this step

The skill run is complete. The `trap cleanup EXIT` handler registered in Step 0
should now be a no-op (sentinel already removed). Confirm the handler exits
cleanly.

The spine is live. Future sessions navigate by following cross-links between
PRODUCT_SENSE.md, DESIGN.md, ARCHITECTURE.md, and QUALITY_SCORE.md directly —
no routing aid needed.

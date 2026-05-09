# Stability Protocol

The intents tree is meant to be a calibration target. Calibration only works if the target sits still. Naive re-clustering on every run scrambles cluster identities even when the underlying claims are nearly the same — k-means is sensitive to initialization, embedding model swaps, and small additions. This document defines the protocol that keeps the tree stable across regenerations.

## Why stability, concretely

Downstream consumers — typically an evaluation layer that scores how well some other system covers customer needs — pin to specific intent node IDs. If `L3.compliance_reporting.annual_report.late_filing_evidence` exists today and is replaced by `L3.regulatory.deadlines.cluster_47` after the next run, the eval breaks silently. A score of "82% coverage of last month's tree" is not comparable to "82% of this month's tree" if the trees aren't the same trees.

So: **identity-preserving updates are the contract.** Adding new nodes is allowed and expected. Renaming, merging, splitting, and deleting are gated.

## State

Three files in `state/`:

- `intent_tree.json` — the working tree. Source of truth for node IDs, titles, centroids, and claim assignments.
- `claim_library.jsonl` — append-only claim library. Source of truth for claim text and source citations.
- `unassigned_pool.jsonl` — claims that didn't fit any existing leaf during incremental assignment. Lives until the discovery pass empties it (or until the user explicitly drops it).

A fourth file, `state/audit_log.jsonl`, records every protocol-relevant event: node created, node renamed, claim assigned, claim moved between nodes, drift threshold crossed, human approval granted. Events are append-only with timestamps. The audit log is what makes the tree's evolution reviewable.

## Thresholds (defaults, all overridable in `state/protocol_config.json`)

| Threshold | Default | What it controls |
|---|---|---|
| `assignment_threshold` | 0.65 cosine similarity | Above this, a new claim is assigned to its nearest existing leaf. Below, it goes to the pool. |
| `discovery_pool_size` | 50 claims | When the pool reaches this, run cluster discovery on it. |
| `discovery_min_cluster_size` | 5 claims | A discovered cluster smaller than this is discarded (probably noise). |
| `parent_fit_threshold` | 0.55 cosine similarity | A new leaf attaches to the existing L2 (or L1, if no L2) whose centroid it's closest to, if similarity ≥ this. Below, it's flagged for human review. |
| `drift_threshold_warn` | 0.20 cosine distance | Centroid drift above this since last anchor → warning in run report. |
| `drift_threshold_block` | 0.40 cosine distance | Above this, no further claims are auto-assigned to that leaf until re-anchored. |
| `merge_candidate_threshold` | 0.95 cosine similarity | Two leaves whose centroids are this close are flagged as merge candidates. |
| `retention_floor` | 5 claims | A leaf with fewer than this for `retention_floor_runs` consecutive runs is flagged for absorption review. |
| `retention_floor_runs` | 3 | How many runs a leaf can be tiny before flagging. |

These are knobs, not laws. Override per-corpus in `state/protocol_config.json`. The protocol is defined by the *behaviours* below, parameterised by these values.

## Behaviours

### 1. Incremental assignment

For each new claim's embedding `e`:

1. For each existing leaf node, compute `cosine_similarity(e, leaf.centroid)`.
2. Pick the highest-similarity leaf.
3. If similarity ≥ `assignment_threshold` AND that leaf's `centroid_drift_since_anchor` < `drift_threshold_block`:
   - Add the claim's ID to the leaf's `claim_ids`.
   - Update the leaf's centroid as a running mean: `new_centroid = (old_centroid * old_count + e) / (old_count + 1)`.
   - Append an `claim_assigned` event to the audit log.
4. Otherwise, append the claim to `state/unassigned_pool.jsonl`. Do not log this as a "rejection" — the pool is a normal staging area.

A leaf that has crossed `drift_threshold_block` is "frozen" — it accepts no new assignments until re-anchored. This prevents drift compounding silently.

### 2. Discovery

Run when pool size ≥ `discovery_pool_size`, or on user demand.

1. Embed all pool claims (already done at extraction time; this is a read).
2. Estimate `k` via the elbow method on within-cluster sum of squares for `k ∈ [2, min(15, pool_size / 5)]`. If the elbow is unclear (no clear inflection), default to `k = 5` and let the human cull empty/redundant clusters at naming time.
3. Run k-means with `k_seeds=10` and pick the lowest-inertia clustering.
4. For each resulting cluster of size ≥ `discovery_min_cluster_size`:
   a. Pick 5 exemplar claims closest to the cluster centroid.
   b. **The subagent reads those exemplars and proposes a Level 3 title and short summary.** This is an LLM-judgment step, not a deterministic one.
   c. Compute the new centroid's similarity to every existing L2 centroid. Highest-similarity L2 above `parent_fit_threshold` → that's the parent. If no L2 fits, try L1s. If no L1 fits, the cluster is a `proposed_new_l1` — flagged, not auto-created.
   d. Generate a slug (lowercase, hyphenated, derived from the title). Suffix with a hash if the slug collides with an existing sibling. Construct the leaf's `id`.
   e. Add the leaf to the tree. Move pool claims into its `claim_ids`. Anchor its centroid (record current centroid as the anchor).
5. Pool claims that ended up in below-`min_cluster_size` clusters stay in the pool — they accumulate for the next discovery pass.
6. Append a `cluster_discovered` event for each new leaf to the audit log, plus a `proposed_new_l1` event for each unfit cluster.

### 3. Anchoring and drift

Every leaf records its centroid at "anchor time" and tracks current centroid drift. Anchor events:

- **Initial creation.** Anchor = the centroid at the moment the leaf was created from a discovery pass.
- **Re-anchoring through `--audit`.** A human runs `cluster_incremental.py --audit --re-anchor <leaf_id>`. The current centroid becomes the new anchor; drift resets.
- **Embedding model change.** All centroids are re-anchored at zero (drift = 0) because the geometry changed. This is a major event; the publish increments `schema_version`'s minor and the run report calls it out.

Drift behaviour:

- `centroid_drift_since_anchor` ≥ `drift_threshold_warn` → warning in run report and `human_review_flags`.
- ≥ `drift_threshold_block` → leaf is frozen as in §1.
- The audit log records every threshold crossing.

### 4. Merge candidates

After every discovery pass, compute pairwise centroid similarity across all leaves. Pairs above `merge_candidate_threshold` are emitted as `merge_candidate` flags. Merging is never automatic. The human runs `cluster_incremental.py --merge <leaf_a> <leaf_b> --new-id <slug>` to act on the suggestion. The merge:

- Creates a new leaf (or reuses one of the two — the human chooses).
- Reassigns all claims from the source leaves to the merged leaf.
- Marks the source leaf IDs as `merged_into: <new_id>` so consumers following old IDs can redirect once.
- Logs `nodes_merged`.

The merged leaf's centroid is the weighted mean of the source centroids. It's anchored at creation.

### 5. Tiny leaves

A leaf below `retention_floor` for `retention_floor_runs` consecutive runs is a `tiny_leaf` flag. It's not auto-deleted. The human can:

- **Absorb** — `cluster_incremental.py --absorb <leaf> <parent_or_sibling>`. Moves the claims, removes the leaf, logs `node_absorbed`.
- **Promote** — adjust thresholds so future similar claims attach to the leaf rather than the pool.
- **Keep** — explicitly mark `retention_pinned: true` in the working state so it stops being flagged. Useful when a leaf represents a low-frequency but high-importance intent.

### 6. Embedding model change

Changing the embedding model invalidates all centroids and all stored embeddings. The protocol around this:

1. The new model name is recorded in `protocol_config.json` and bumped explicitly. Don't pick up the model from a default that quietly changed across `pip install` versions.
2. Re-embed every claim in the library against the new model. Cache embeddings.
3. Recompute every leaf centroid as the mean of its claims' new embeddings.
4. Re-anchor every leaf at the new centroid; drift resets.
5. Recompute the unassigned pool's clusters from scratch — but the resulting clusters are reconciled against existing leaves first by name + sample similarity, not just centroid similarity, before anything new is created.
6. The publish bumps `schema_version` minor and notes the model change in `publish_metadata`.

This is rare; it should happen at most a few times per year. When it does, treat it as a major change with extra human review.

## Run-time invariants

These should always be true after a successful run. The publish script asserts them; failure is a hard error, not a warning.

- Every claim ID in any leaf's `claim_ids` exists in `claim_library.jsonl`.
- Every claim in `claim_library.jsonl` is either in exactly one leaf's `claim_ids` OR in `unassigned_pool.jsonl`.
- No leaf appears under more than one parent.
- Every node ID matches the format `L<n>.<slug>...` where the prefix matches the parent chain.
- `centroid_drift_since_anchor` is non-negative.
- `tree_hash` in the most recent publish equals the fresh hash of the current working tree (computed by the same canonicalization).

If any invariant is violated, the run aborts before publish, the working state is rolled back to a snapshot taken at run start, and the failure is reported.

## What the human is for

This protocol delegates everything below "obviously safe" to the human. That is intentional. Auto-merging on a high centroid similarity sounds harmless until two intents that *look* close (e.g., "Annual report deadline questions" and "Quarterly report deadline questions") collapse into one and the calibrator now misses a real distinction.

The subagent's job is to surface candidates, not to take destructive actions. The human runs `--audit` and decides. Most runs need no human action — the protocol is designed so the additive case (new claims, occasional new leaves) is fully automated. Refactoring is the gated case.

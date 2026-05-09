# Intent Tree Schema & IIntentTreeSource Contract (v1.0)

The intents tree is the second deliverable of this subagent. It exists in two forms:

1. **Working state** — `state/intent_tree.json`. Mutable. Updated incrementally on every run.
2. **Published artifact** — `published/intent_tree_v<N>.json`. Immutable. What downstream `IIntentTreeSource` consumers read.

The two forms share the same JSON shape; the published version adds version metadata and is content-hashed.

## Shape

```json
{
  "schema_version": "1.0",
  "publish_metadata": {
    "version": 7,
    "generated_at": "2026-05-07T13:42:11Z",
    "tree_hash": "sha256:abc123...",
    "parent_hash": "sha256:def456...",
    "parent_version": 6,
    "extractor_version": "conversation-distillation@1.0",
    "embedding_model": "BAAI/bge-base-en-v1.5"
  },
  "stats": {
    "total_claims_in_library": 12453,
    "claims_assigned": 12289,
    "claims_in_unassigned_pool": 164,
    "level_1_count": 8,
    "level_2_count": 31,
    "level_3_count": 87,
    "new_nodes_this_run": {"l1": 0, "l2": 1, "l3": 4},
    "human_review_flags": [
      {"kind": "proposed_new_l1",
       "centroid_summary": "Claims about merger and acquisition disclosures",
       "claim_count_in_pool": 73}
    ]
  },
  "tree": [
    {
      "id": "L1.compliance_reporting",
      "level": 1,
      "title": "Compliance & Regulatory Reporting",
      "summary": "Customer questions and agent answers about mandatory regulatory filings, deadlines, and compliance procedures.",
      "first_seen_run": 1,
      "first_seen_at": "2026-04-01T09:12:33Z",
      "claim_count": 5230,
      "last_modified_run": 7,
      "centroid_age_runs": 7,
      "centroid_drift_since_anchor": 0.04,
      "children": [
        {
          "id": "L2.compliance_reporting.annual_report",
          "level": 2,
          "title": "Annual Report Submission",
          "summary": "Filing of annual reports including 10-K and equivalent disclosures.",
          "first_seen_run": 1,
          "claim_count": 1840,
          "centroid_drift_since_anchor": 0.02,
          "children": [
            {
              "id": "L3.compliance_reporting.annual_report.late_filing_evidence",
              "level": 3,
              "title": "Requirements for evidence of system failure during late filing",
              "summary": "Specific documentation customers must provide when claiming a technical system outage caused a missed filing deadline.",
              "first_seen_run": 4,
              "claim_count": 47,
              "claim_ids": ["c_a8f2c1d49b03", "c_b7e1a2f33c4d", "..."],
              "centroid": [0.0123, -0.0045, "..."],
              "centroid_drift_since_anchor": 0.01,
              "exemplar_claims": [
                "c_a8f2c1d49b03",
                "c_b7e1a2f33c4d",
                "c_c4d8a59b1e02"
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

## Field semantics

### `publish_metadata`

`version` — monotonically increasing integer. Bumped on every publish, even if no nodes changed.

`tree_hash` / `parent_hash` — sha256 of the canonical JSON of `tree` (sorted keys, no whitespace). Lets a consumer detect changes without diffing the whole document and trace the provenance chain. Tampering with a published file breaks the chain.

`extractor_version` — version string of the subagent + extraction prompt that produced the underlying claims. Bumping it signals "claim quality is not strictly comparable to prior versions". Downstream calibrators should record this.

`embedding_model` — which embedding model produced the centroids. Centroids from different models are not interchangeable; if this changes, all centroids must be recomputed, which is a re-anchoring event.

### `stats.human_review_flags`

Things the run flagged but did not act on. The downstream consumer can ignore these (they're not part of the tree) but they're carried in the publish so a human reviewing the published artifact knows what the subagent declined to do silently. Common flags:

- `proposed_new_l1` — pool yielded a candidate cluster that didn't fit any existing L1.
- `centroid_drift_warning` — a leaf's centroid moved past the drift threshold.
- `merge_candidate` — two leaves now have centroid similarity above the merge threshold (default 0.95).
- `tiny_leaf` — a leaf has fewer than the retention floor (default 5 claims) for more than N runs; downstream can decide whether to absorb or keep.

### `tree[]`

An array of L1 nodes, each with nested `children`. Three depth levels max. A node has children only if its content warrants subdivision; an L1 with only ~50 claims may have no L2 children, which is fine.

### Node fields

`id` — stable identifier. Format: `L<level>.<l1_slug>[.<l2_slug>[.<l3_slug>]]`. Slugs are immutable once assigned; renaming a node updates `title` but never `id`. Downstream calibrators reference nodes by `id` and depend on it being stable.

`title` — the LLM-assigned name. Editable by humans through `--audit`.

`summary` — one-to-three-sentence description of what claims belong here. LLM-generated when the node is created; refined when the node is materially refactored.

`first_seen_run` / `first_seen_at` — when this node first appeared. Persists through subsequent runs unchanged. Calibrators can use this to detect "this intent emerged after our last calibration baseline".

`claim_count` — number of claims currently in this node's subtree. For L1/L2, this includes all descendants.

`centroid` — present only on L3 leaves (and on L2 leaves that have no L3 children). The 768-dim (or whatever the embedding model produces) running-mean vector. Mid-level nodes' centroids are derived as means of their children's centroids; the publish script computes them but doesn't store them on inner nodes to keep file size manageable.

`centroid_drift_since_anchor` — cosine distance between the current centroid and the centroid recorded at the last "anchor" event. Anchoring happens at node creation and at human-approved re-anchoring through `--audit`. A high drift value means "this node's claims have semantically moved since anchoring" — it doesn't auto-trigger anything, but it surfaces in `human_review_flags`.

`exemplar_claims` — three to five claim IDs that are representative of this node. Useful for downstream consumers showing "what does this intent look like?" without loading every claim. Picked as the claims closest to the centroid.

`claim_ids` — full list of every claim assigned to this leaf. Present only on leaves; mid-level nodes don't duplicate this.

## What the published file is for

The `IIntentTreeSource` interface is owned by downstream calibration code and is not defined in this repository. From the perspective of this subagent, the contract is:

- Each published JSON is consumed in full or not at all (no partial reads).
- Consumers identify nodes by `id`, never by position.
- Consumers tolerate the addition of new fields without breaking. Removal of documented fields requires bumping `schema_version`.
- Consumers can rely on `id` stability across publishes within the same `schema_version`.

## What stability looks like in the published artifact

When you compare `intent_tree_v6.json` against `intent_tree_v7.json`, the expected diff after a normal run is:

- Every existing `id` is still present.
- Every `id` has the same `title` (or, rarely, a human-edited title — flagged in `stats.new_nodes_this_run` as edits, not adds).
- `claim_count` values increase or stay the same; they don't decrease.
- `claim_ids` arrays grow — they don't shed entries.
- Some new `id` values may appear under existing parents (new L3 leaves; rarely new L2; almost never new L1).
- `centroid` values shift slightly (new claims pulled the mean) but `centroid_drift_since_anchor` should generally stay below the anchor threshold.

If a published version shows wholesale renaming of IDs, dropped IDs, or large drift, that is a bug — either in the subagent or in the run command that bypassed `--audit`. The downstream calibrator should detect this through hash-chain comparison and alert.

## What the working state looks like

`state/intent_tree.json` is the same shape minus `publish_metadata` and minus the centroids and claim_ids being copied for publish (the working state stores them once on the leaves). The publish script is read-only against the working state — it copies data, doesn't transform it.

If you ever find the working state diverging from the most recent publish, that's a bug — they should agree at publish time. The subagent's run report includes a sanity check that the most-recent publish's `tree_hash` matches a fresh hash of the working state at run end.

## Feature slug

intent-tree-construction

## User job

When building the knowledge base, the analyst wants to cluster atomic claims into a 2-3 level intent tree so that semantic drift between colloquial language and official documentation is reduced.

## Acceptance behavior

The system produces a stable 2-3 level intent tree (L1 business category, L2 process stage, L3 specific intent) from atomic claims, with cross-verification against the top-down computation graph.

## Tiebreaker citations

- Scoring accuracy vs. throughput — accuracy wins. The intent tree must correctly map claims to nodes; speed of clustering is secondary to semantic correctness.
- Shared infrastructure vs. product-specific UX — product-specific UX wins. The tree structure must serve the specific RegTech domains (CA, e-seals, corporate registration) rather than a generic taxonomy.

## Open questions

- How is "stable" defined — by week-over-week Jaccard similarity of L3 nodes?
- What manual review process is required before a new L3 node is promoted to production?

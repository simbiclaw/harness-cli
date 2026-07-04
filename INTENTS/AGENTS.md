# INTENTS tree — agent instructions

This tree is the single source of behavioural truth for the Argus/Metis/Hermes platform. Agents read from it; agents write to it through the transformation layer's build pipeline. See `docs/product-specs/shared/intents-semantic-layer.md` for the full layout and naming grammar.

## Reading the tree

- Walk the directory structure — the path IS the ontology.
- Pin to a specific git SHA via `argus.intents_sha`.
- Use the INTENTS Provider (`argus.io`) for typed reads.
- `_meta/ownership.yaml` tells you which producer owns each file.

## Writing to the tree

- Do NOT write directly. Updates go through the transformation layer's build pipeline (audio2tree, doc2graph, Navigator).
- Every file must be owned by exactly one producer (enforced by structural test).
- Slugs are demand-minted from customer language. Renaming a slug is a breaking change.

## Structural invariants (CI-enforced)

- Every `.yaml`/`.json`/`.jsonl` parses.
- Every file matches exactly one producer glob in `_meta/ownership.yaml`.
- Every `ui_binding_ref` in a capsule Bone (`index.md`) resolves to a `ui_step` in a Flesh file.

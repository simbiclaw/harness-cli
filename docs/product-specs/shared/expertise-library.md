---
verification-status: proposed
last-reviewed: bootstrap
consumed-by: Argus, Metis, Hermes
---

# Expertise Library (shared)

The seven expertise modules consumed by the three apps. Each module has its own update cadence, ownership, and consumer set. Bundling them would force false uniformity; this spec keeps them differentiated.

The library is **read-only at runtime**. All three apps consume; none of them write at runtime. Updates to the expertise modules happen via separate offline pipelines — deliberately, to prevent runtime feedback loops from inflating the library's authority.

## Consumer matrix

| Module | Argus | Metis | Hermes | Update cadence |
|---|---|---|---|---|
| Rules & Criteria | ✓ | — | ✓ | low (rules ship in policy releases) |
| Acoustic Feature | ✓ | — | — | low (model versions) |
| Product Introduction | ✓ | ✓ | ✓ | medium (product changes) |
| Operation Manual | ✓ | — | ✓ | medium (manual updates → triggers `document-ingestion.md`) |
| Dynamic Knowledge Base | ✓ | — | ✓ | high (FAQ, current policies) |
| Best Practice Cookbook | ✓ | — | ✓ | medium (curated examples) |
| Error Case Library | ✓ | — | ✓ | high (self-learning loop from reviewer overrides) |
| Phrase & Keyword Library | ✓ | — | ✓ | medium (sensitive/negative word lists; ASR lexicon biasing) |
| Audio Transcription | ✓ | ✓ | ✓ | per-call (output of `audio-intake.md`) |

(The PRD's expertise table is reproduced verbatim above with the addition of update cadence; none of the consumer assignments are invented.)

Notes:
- **Metis is intentionally thin in this matrix.** Metis primarily operates on the calibrated graph, the intents-tree, and the per-call atomic claims; it consumes Product Introduction for context when surfacing tickets but does not need the rule sets or operational manuals at runtime. This thinness is reflected in the dependency matrix in `ARCHITECTURE.md § 3` (Metis's `IExpertiseReader` access is marked "selective").
- **Hermes consumes Operation Manual indirectly** via the calibrated graph that derives from it; the entry in this matrix records the original-source dependency, not a direct read at runtime.

## Module shapes (interfaces)

Each module exposes a typed reader. All readers are declared in `ExpertiseLibrary/Types`, in line with the `ARCHITECTURE.md § 3` interface-single-declaration rule.

```
IRulesAndCriteriaReader     → grading rules and scoring criteria
IAcousticFeatureReader      → reference acoustic patterns for QA
IProductIntroductionReader  → product features, specs, scenarios
IDynamicKnowledgeBaseReader → real-time-updated policy, FAQ
IBestPracticeCookbookReader → curated effective methods
IErrorCaseLibraryReader     → patterns from past errors (self-learning)
IPhraseKeywordReader        → sensitive/negative/recommended phrase lists
```

The `IExpertiseReader` referenced in `ARCHITECTURE.md § 3` is a fac̀ade type that exposes the seven readers as a single bounded surface; consumers depending on `IExpertiseReader` rather than the individual readers carry intent ("this consumer reads expertise broadly"); consumers depending on a specific reader carry stronger intent ("this consumer needs only rules-and-criteria"). Both are permitted.

## Update mechanisms

Each module's update path is documented separately because each has different consequences:

**Rules & Criteria**: human-authored. Updates ship as policy releases; the lint `rules-version-pinned` ensures every Argus run records the rules-version it scored against, preventing retroactive blame for scores produced under a prior policy.

**Acoustic Feature**: model-derived. Updates ship as model versions; reproducibility requires recording the model version per use.

**Product Introduction**: human-authored. Updates ship with product releases.

**Operation Manual**: human-authored, often by external operations teams. Updates trigger `document-ingestion.md` regeneration of the compute-graph, which triggers `calibration.md` recalibration.

**Dynamic Knowledge Base**: human-authored, frequent. Updates do not require recalibration of the compute-graph; they update at the consumer's read-time. Cache invalidation is per-reader.

**Best Practice Cookbook**: curated, additive. New entries do not invalidate prior decisions.

**Error Case Library** (self-learning): updated automatically from reviewer overrides in Argus. **This is the only expertise module with a runtime-fed update path, and the path is explicitly offline-batched, not real-time**. Reviewer overrides accumulate; a periodic offline job (initial cadence: nightly) processes the accumulated overrides into new error-case entries; a human approves the proposed update before it ships. The approval gate prevents a runtime feedback loop where a single reviewer's override propagates into the library and influences future Argus verdicts within the same session.

**Phrase & Keyword Library**: human-authored, with periodic review of high-frequency terms emerging from `conversation-distillation.md` claims (a candidate-list pipeline surfaces new domain terms; humans approve before they enter the lexicon for ASR biasing).

## Failure modes and tolerances

**Module read fails at runtime**: every consumer must handle reader failure gracefully. For Argus: fail closed (do not score; mark the call `requires-review`). For Metis: degrade (surface ticket without expertise context). For Hermes: refuse to act (Tier-B and Tier-C cannot proceed without expertise context; Tier-A may proceed read-only).

**Module versions skew across consumers**: Argus reads rules-version 12 while Hermes reads operation-manual-version 11 derived from a graph calibrated against rules-version 11. Detected by version-tracking metadata on every reader call; surfaced as a system alert. The mitigation is offline coordination, not runtime sync.

## Forbidden behaviours

No runtime writes. No silent merging of conflicting expertise versions. No stripping of version metadata from reader returns (every read carries the version of the source it came from; downstream uses that for evidence-citing in audit trails).

## Tiebreaker references

- `PRODUCT_SENSE.md § Argus` — failure tolerance "score without traceable evidence is a release blocker" depends on Rules & Criteria evidence-citing.
- `PRODUCT_SENSE.md § Hermes` — refuse-to-act on missing expertise context.
- `PRODUCT_SENSE.md § Cross-product` — read-only-at-runtime.

## Open questions

> **Question**: What is the ownership model for each module? Who is responsible for keeping Rules & Criteria current? Who curates the Best Practice Cookbook?
> **Default if not decided**: human ownership per module to be assigned in an ADR before the modules are populated beyond bootstrap stubs. Until then, every module has a placeholder `OWNER: TBD` field.

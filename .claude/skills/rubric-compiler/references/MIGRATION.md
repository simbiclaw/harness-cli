# Migration: Option B (this skill) -> Option A (production CLI)

Trigger (SPEC section 7): v2 execution env lands, or blocking machinery is
introduced - or the hard-test protocol passes and you want load-bearing
enforcement.

What moves where:
1. Loop control, R bound, hold/release, batching -> Python driver
   (`harness-cli` app, e.g. `apps/compiler/`), agents via Claude Agent SDK.
   SKILL.md's workflow section becomes driver code; agents/*.md become SDK
   system prompts, unchanged.
2. gate.py -> promote to `tools/` ring-2; wire `precompile`, `item`, `rg`,
   epoch check into harness.yml CI. Gate code itself should need zero changes
   - that is the point of writing it as a standalone script now.
3. config/ (adjectives, frames, expertise types) -> versioned gate inputs
   with an owner and epoch-commit review (O6).
4. Evaluator seam: `evaluate(proposal, referents, execution_env=None)` grows
   the v2 env (sample + adversarial call logs). Interface stays fixed.
5. Keep runs/ layout byte-compatible so T7 metrics remain comparable across
   the migration.
What must NOT migrate: any accept path that bypasses the gate; any spec write
access; unbounded rounds.

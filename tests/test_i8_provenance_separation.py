"""Standing I8 fixture — provenance separation (9020 M5).

I8: logit-derived continuity is proposer-internal and MUST NOT reach any
disposer input — specifically no logit-derived quantity may feed `severity_map`,
`deduction`, coverage, criterion health, or routing. The anticipated failure is
a well-meaning simplification ("we already have a continuous signal, use it for
severity"), which converts the human anchor into a model self-report. This
fixture makes that a test failure rather than a design discussion.

Two enforcement surfaces, matching the plan:
  - a red/green pair over code SAMPLES, so the check is exercised on the exact
    violation it targets (the disposer modules themselves are 9002's and largely
    unstarted); and
  - a live scan of `src/argus/core/**`, so the invariant guards the real tree
    as its disposer stages land.

Pairs with the companion patch's Gate-Checkability Audit: a quantity is only
gate-checkable if a deterministic check can confirm its referent — observed
once in compiled item signals, once here in proposer scores.

See docs/exec-plans/active/9020-continuous-proposer-and-provenance-separation.md
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORE = REPO_ROOT / "src" / "argus" / "core"

# Symbols whose value is logit-derived — a model self-report (D19 quarantine).
LOGIT_DERIVED = {
    "proposed_score", "proposed_scores", "dimension_logits",
    "ProposedScores", "logit", "logits", "logprob", "logprobs",
    # 9021 M9. `proposed` and `proposed_upper` are how the quantity is actually
    # spelled where it is read: M20's drift probe takes `probe_divergence(
    # proposed, derived)` and `to_common_axis(..., upper=proposed_upper)`. The
    # set previously listed only `proposed_score`, so the checker could not see
    # the one call site in the tree that genuinely handles a logit-derived
    # number — `severity = proposed` inside `divergence.py` would have passed.
    # Matching is on exact identifiers, so this does not catch `ProposedFinding`
    # or `proposed_findings`.
    "proposed", "proposed_upper",
}

# Disposer sinks I8 names. A logit-derived value reaching any of these is the
# violation: the shipped severity/deduction/coverage/health/routing must resolve
# through grounded evidence and the human-annotated manifest, never a self-report.
DISPOSER_SINKS = {
    "severity_map", "severity", "deduction", "coverage",
    "criterion_health", "routing", "auto_final", "raw", "adjusted",
}


def _names_in(node: ast.AST) -> set[str]:
    """Every identifier (Name id or Attribute attr) appearing under a node."""
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def _referenced_logit_symbols(tree: ast.AST) -> set[str]:
    """Logit-derived symbols a module actually *uses* — not ones it talks about.

    9021 M9. The live scan previously decided "is a reader" with
    `"proposed_score" in code`, a raw substring over the file. That was a
    reasonable backstop while `core/` held two modules and no prose; once the
    tree grew it fired on `core/grounding.py`, whose only mention of the symbol
    is a docstring sentence explaining that the field is *refused*. A module
    documenting that it rejects a value is the opposite of a reader, and
    allowlisting it would have widened the allowlist to admit a non-violation —
    which the acceptance property forbids just as firmly as admitting a real one.

    So the check is now structural. It counts three uses and no prose:
      - an identifier (`proposed_score`, `x.logprobs`);
      - a string used as a subscript key (`payload["proposed_score"]`);
      - a string passed to an attribute-or-mapping accessor
        (`getattr(r, "logits")`, `d.get("proposed_score")`).

    The string forms are why this is a tightening rather than a deletion:
    dropping the substring check outright would have lost `d["proposed_score"]`,
    which the identifier walk alone does not see.
    """
    found = _names_in(tree) & LOGIT_DERIVED

    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant):
            if n.slice.value in LOGIT_DERIVED:
                found.add(n.slice.value)
        elif isinstance(n, ast.Call):
            accessor = ""
            if isinstance(n.func, ast.Attribute):
                accessor = n.func.attr
            elif isinstance(n.func, ast.Name):
                accessor = n.func.id
            if accessor in {"get", "getattr", "pop", "setdefault"}:
                for a in n.args:
                    if isinstance(a, ast.Constant) and a.value in LOGIT_DERIVED:
                        found.add(a.value)

    return found


def _target_sink(target: ast.AST) -> str | None:
    """The disposer-sink name a target writes to, if any.

    Handles `severity_map[x] = ...`, `self.severity_map = ...`, `severity = ...`.
    """
    node = target
    if isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Attribute) and node.attr in DISPOSER_SINKS:
        return node.attr
    if isinstance(node, ast.Name) and node.id in DISPOSER_SINKS:
        return node.id
    return None


def i8_violations(code: str) -> list[str]:
    """Return I8 violations in a code sample: a logit-derived value → a disposer sink.

    Deterministic and referent-confirming: it flags an assignment whose target
    is a disposer sink and whose right-hand side references a logit-derived
    symbol, plus the call form `set_severity(proposed_score)` where a
    disposer-named setter is handed a logit-derived argument.
    """
    tree = ast.parse(code)
    violations: list[str] = []

    for node in ast.walk(tree):
        targets: list[ast.AST] = []
        value: ast.AST | None = None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets, value = [node.target], node.value
        if value is not None:
            rhs = _names_in(value)
            for tgt in targets:
                sink = _target_sink(tgt)
                if sink and (rhs & LOGIT_DERIVED):
                    src = ", ".join(sorted(rhs & LOGIT_DERIVED))
                    violations.append(f"line {node.lineno}: {sink} <- {src}")

        # Call form: a disposer-named setter handed a logit-derived argument.
        if isinstance(node, ast.Call):
            fname = ""
            if isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            elif isinstance(node.func, ast.Name):
                fname = node.func.id
            if any(sink in fname for sink in DISPOSER_SINKS):
                argnames: set[str] = set()
                for a in list(node.args) + [kw.value for kw in node.keywords]:
                    argnames |= _names_in(a)
                if argnames & LOGIT_DERIVED:
                    src = ", ".join(sorted(argnames & LOGIT_DERIVED))
                    violations.append(f"line {node.lineno}: {fname}(<- {src})")

    return violations


# --- Red/green samples -----------------------------------------------------

RED_SEVERITY = """
def dispose(finding, proposed_score, manifest):
    severity_map = {}
    severity_map[finding.criterion] = proposed_score   # I8 violation
    return severity_map
"""

GREEN_SEVERITY = """
def dispose(finding, proposed_score, manifest):
    severity_map = {}
    severity_map[finding.criterion] = manifest.severity(finding.criterion)
    return severity_map
"""


def test_i8_red():
    """A logit-derived quantity reaching severity_map is structurally rejected."""
    violations = i8_violations(RED_SEVERITY)
    assert violations, "the fixture failed to catch proposed_score → severity_map"
    assert any("severity_map" in v for v in violations)


def test_i8_green():
    """severity_map resolving only through the calibration manifest passes."""
    assert i8_violations(GREEN_SEVERITY) == []


def test_i8_covers_all_disposer_inputs():
    """The same rejection holds for deduction, coverage, criterion health, routing."""
    for sink in ("deduction", "coverage", "criterion_health", "routing"):
        red = f"""
def dispose(proposed_score):
    {sink} = proposed_score
    return {sink}
"""
        green = f"""
def dispose(grounded, manifest):
    {sink} = manifest.resolve(grounded)
    return {sink}
"""
        assert i8_violations(red), f"{sink}: violation not caught"
        assert i8_violations(green) == [], f"{sink}: false positive on a clean path"


def test_a_module_that_only_names_the_symbol_in_prose_is_not_a_reader():
    """9021 M9 — the regression that motivated the structural check.

    `core/grounding.py` documents that it *refuses* a proposed score. Counting
    that as a read forced a choice between two wrong answers: allowlist a module
    that reads nothing, or call a docstring an I8 violation.
    """
    prose_only = '"""ProposedFinding forbids proposed_score=0.4 at construction."""\n\ndef ground(findings):\n    # logits are a proposer concern and never arrive here\n    return findings'
    assert _referenced_logit_symbols(ast.parse(prose_only)) == set()


def test_string_keyed_access_is_still_a_read():
    """The tightening must not lose what the substring check was there for.

    `payload["proposed_score"]` never appears as an identifier, so the AST
    name walk alone would miss it. These are the forms that keep it caught.
    """
    for code in (
        'def f(payload): return payload["proposed_score"]',
        'def f(r): return getattr(r, "logprobs")',
        'def f(d): return d.get("proposed_score")',
        'def f(r): return r.logits',
        'def f(proposed_score): return proposed_score',
    ):
        assert _referenced_logit_symbols(ast.parse(code)), code


def test_i8_call_form_is_caught():
    """The setter-call form is caught too, not only direct assignment."""
    red = "def d(proposed_score, m): m.set_severity(proposed_score)"
    green = "def d(grounded, m): m.set_severity(m.manifest_lookup(grounded))"
    assert i8_violations(red)
    assert i8_violations(green) == []


def test_divergence_is_the_only_permitted_reader():
    """No core module feeds a logit-derived quantity into a disposer sink, and the
    only core readers of a logit-derived quantity are divergence (drift input) and
    escape_sampler (review ordering) — both non-disposer uses.

    Refined from the plan's literal "sole reader": M4's escape_sampler legitimately
    reads proposed_score to ORDER the prioritized human-review tranche, which is
    not a disposer input. The load-bearing I8 property is that no core module
    routes a logit-derived value into a disposer sink; that is asserted directly.
    See the Decision Log.
    """
    assert CORE.exists()
    ALLOWED_READERS = {"divergence.py", "escape_sampler.py"}

    disposer_violations: dict[str, list[str]] = {}
    readers: set[str] = set()
    for py in sorted(CORE.rglob("*.py")):
        if py.name == "__init__.py":
            continue
        code = py.read_text()
        v = i8_violations(code)
        if v:
            disposer_violations[py.name] = v
        # A "reader" uses a logit-derived symbol — structurally, not in prose.
        if _referenced_logit_symbols(ast.parse(code)):
            readers.add(py.name)

    assert not disposer_violations, (
        f"core modules feed a logit-derived quantity into a disposer sink (I8): "
        f"{disposer_violations}"
    )
    stray = readers - ALLOWED_READERS
    assert not stray, (
        f"unexpected core modules read a logit-derived quantity: {stray}. Either "
        f"the read is a disposer input (an I8 violation) or the allowlist needs a "
        f"reviewed update with a Decision Log entry."
    )
    assert "divergence.py" in readers, "divergence must read the proposed score (drift input)"


def test_the_drift_probe_is_seen_through_the_name_it_actually_uses():
    """9021 M9 — the hole the structural reader check exposed.

    Before M9 this assertion passed on `divergence.py`'s *docstring*: the module
    spells the quantity `proposed`, which was not in `LOGIT_DERIVED`, and the
    substring scan matched the prose instead. So the checker was reporting the
    right answer for the wrong reason, and a real violation written in the same
    vocabulary would have gone through.
    """
    source = (CORE / "divergence.py").read_text()
    assert _referenced_logit_symbols(ast.parse(source)), (
        "the drift probe's logit-derived input is invisible to the checker"
    )
    planted = "def probe(proposed):\n    severity = proposed\n    return severity\n"
    assert i8_violations(planted), (
        "a logit-derived value reaching a disposer sink under the drift probe's "
        "own parameter name must still be an I8 violation"
    )

"""Acceptance tests for M4 — Agreement seeder + deduction setter (9003).

RED phase: these tests fail until `src/argus/core/compiler/agreement.py` is
implemented (module import error = the documented RED state; committed only
when green).

Pure functions per the plan's M4 contract: A5 seed_agreement_gate, A6
set_deduction_weight + set_w_c, A7 set_iteration_policy.
"""

from __future__ import annotations

from argus.core.compiler.agreement import (
    seed_agreement_gate,
    set_deduction_weight,
    set_iteration_policy,
    set_w_c,
)
from argus.core.compiler.validator import check_escape_plan


def make_criterion(**overrides) -> dict:
    criterion = {"id": "C22", "description": "情绪安抚：先安抚再处理"}
    criterion.update(overrides)
    return criterion


def make_item(**overrides) -> dict:
    item = {
        "id": "22",
        "text": "情绪安抚：客户情绪激动时先安抚再处理",
        "values": {"named_phrases": ["您别着急"], "numeric_thresholds": []},
        "deduction_weight": None,
        "corroborators": [],
    }
    item.update(overrides)
    return item


# ── A5: agreement gate seeding ───────────────────────────────────────────────


class TestSeedAgreementGate:
    def test_agreement_block_has_both_tails(self):
        """tau + kappa_sample_plan + escape_sample_plan + escape_ceiling all present."""
        block = seed_agreement_gate(make_criterion())
        assert block["tau"] == 0.8
        assert block["kappa_sample_plan"], "agreement tail must be seeded"
        assert block["escape_sample_plan"], "auto-pass tail must be seeded"
        assert block["escape_ceiling"] is not None
        assert block["current_kappa"] is None, "current_kappa initializes null"

    def test_seeded_block_passes_auth3_and_auth6(self):
        """A seeded block must never trip AUTH-3/AUTH-6 (both tails present)."""
        block = seed_agreement_gate(make_criterion())
        assert check_escape_plan({"agreement": block}) == [], "seeded block must pass AUTH-6"

    def test_missing_escape_plan_rejected(self):
        """kappa plan present but no escape plan → AUTH-6 rejects."""
        node = {"agreement": {"tau": 0.8, "kappa_sample_plan": "rolling 200"}}
        errors = check_escape_plan(node)
        assert errors, "agreement without escape_sample_plan must be rejected (AUTH-6)"


# ── A6: deduction weight ─────────────────────────────────────────────────────


class TestSetDeductionWeight:
    def test_deduction_weight_from_item(self):
        item = make_item(deduction_weight=5.0)
        assert set_deduction_weight(item, "empathy_and_tone") == 5.0

    def test_deduction_default_is_one(self):
        assert set_deduction_weight(make_item(), "empathy_and_tone") == 1.0

    def test_deduction_not_scaled_by_corroboration(self):
        """Corroboration moves routing, never the deduction arithmetic (I6)."""
        item = make_item(
            deduction_weight=2.0,
            corroborators=[{"signal_type": "acoustic_measurement", "node_ref": "call-42/f0"}],
        )
        assert set_deduction_weight(item, "empathy_and_tone") == 2.0


# ── A6: W_C provisional constant ─────────────────────────────────────────────


class TestSetWC:
    def test_w_c_is_provisional_flagged(self):
        result = set_w_c(make_criterion())
        assert result["value"] == 0.4, "W_C = 0.4 PROVISIONAL"
        assert result["provisional"] is True
        note = result["note"]
        assert "PROVISIONAL" in note or "provisional" in note or "measure" in note, (
            "provisional status must be flagged for empirical measurement"
        )

    def test_w_c_shared_constant(self):
        """w_c is an agreement/config constant, not a per-item field (patch-1 D6)."""
        assert set_w_c(make_criterion())["value"] == set_w_c(make_criterion(id="C21"))["value"]


# ── A7: iteration policy ─────────────────────────────────────────────────────


class TestSetIterationPolicy:
    def test_iteration_policy_forbids_model_edits(self):
        policy = set_iteration_policy(make_criterion())
        assert "no rule edits from Argus output" in policy
        assert "epoch commit" in policy, "re-grounding must be write-time epoch commit only"


# ── B-verification fix round (2026-08-12): numeric robustness ───────────────


class TestBFixRound:
    """Findings F1/F2 closed: weight must be finite-real or default 1.0."""

    def test_f1_huge_int_no_crash(self):
        assert set_deduction_weight({"deduction_weight": 10**400, "id": "22"}, "d") == 1.0, (
            "out-of-float-range int must not crash; defaults to 1.0"
        )

    def test_f2_nan_inf_default(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            assert set_deduction_weight({"deduction_weight": bad, "id": "22"}, "d") == 1.0, (
                f"non-finite weight {bad!r} must default to 1.0"
            )


# ── no-crash contract (M1/M2/M3 precedent) ───────────────────────────────────


class TestNoCrash:
    def test_garbage_inputs_no_crash(self):
        for bad in (None, "x", [], 42):
            assert seed_agreement_gate(bad)["kappa_sample_plan"], f"seed_agreement_gate({bad!r}) must not crash"
            assert set_deduction_weight(bad, "d") == 1.0, "set_deduction_weight must not crash"
            assert set_w_c(bad)["value"] == 0.4, "set_w_c must not crash"
            assert set_iteration_policy(bad), "set_iteration_policy must not crash"

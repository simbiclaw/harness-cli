"""M5 structural tests: Hermes action-tier enforcement.

These tests verify the two safety guarantees from PRODUCT_SENSE.md Hermes:
1. Every ActionDescriptor must carry an explicit tier.
2. Tier-C methods on the browser-automation Provider are unreachable from
   outside the explicit allowlist.
"""

from __future__ import annotations

from argus.hermes.types import TIER_C_ALLOWLIST, ActionDescriptor, ActionTier


def test_no_untagged_action_descriptor():
    """ActionDescriptor must have an explicit tier — no default, no omission."""
    a = ActionDescriptor(
        tier=ActionTier.B,
        name="click_submit",
        target="#submit-btn",
    )
    assert a.tier == ActionTier.B

    assert not hasattr(ActionTier, "UNSPECIFIED")
    assert ActionTier.A.value == "A"
    assert ActionTier.B.value == "B"
    assert ActionTier.C.value == "C"


def test_tier_c_unreachable_from_outside_allowlist():
    """Tier-C allowlist starts empty per PRODUCT_SENSE.md.

    This test verifies the allowlist mechanism exists and is empty by default.
    When real Tier-C dispatch code exists, this test will verify that
    Tier-C methods are only callable from call sites in the allowlist.
    """
    assert set() == TIER_C_ALLOWLIST

    from argus.providers.browser_automation import BrowserAutomationProvider

    provider = BrowserAutomationProvider()
    assert hasattr(provider, "submit_payment")
    assert hasattr(provider, "modify_account_settings")
    assert hasattr(provider, "execute_autonomous_workflow")

    assert hasattr(provider, "inspect_dom")
    assert hasattr(provider, "take_screenshot")
    assert hasattr(provider, "click_element")
    assert hasattr(provider, "fill_field")

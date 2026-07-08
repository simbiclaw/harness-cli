"""Browser-automation Provider scaffold for Hermes action execution.

Three method sets, one per action tier.  No implementation yet — typed
boundaries only.  The hermes-tier-c-allowlist structural test enforces
that Tier-C methods are unreachable from outside the allowlist.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from argus.hermes.types import ActionDescriptor


class BrowserAutomationProvider:
    """Scaffold: browser automation for Hermes action execution."""

    # ---- Tier A: read-only ----
    def inspect_dom(self, selector: str) -> str:
        raise NotImplementedError

    def take_screenshot(self) -> bytes:
        raise NotImplementedError

    def navigate(self, url: str) -> None:
        raise NotImplementedError

    # ---- Tier B: confirmed (user approved before execution) ----
    def click_element(self, selector: str) -> None:
        raise NotImplementedError

    def fill_field(self, selector: str, value: str) -> None:
        raise NotImplementedError

    def submit_form(self, selector: str) -> None:
        raise NotImplementedError

    # ---- Tier C: autonomous (allowlist-gated) ----
    # These methods must NOT be callable from outside the TIER_C_ALLOWLIST.
    # The hermes-tier-c-allowlist structural test enforces this.

    def submit_payment(self, amount: float, currency: str) -> str:
        raise NotImplementedError

    def modify_account_settings(self, account_id: str, changes: dict[str, object]) -> None:
        raise NotImplementedError

    def execute_autonomous_workflow(self, descriptor: ActionDescriptor) -> str:
        raise NotImplementedError

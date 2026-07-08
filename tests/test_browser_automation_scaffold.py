"""Tests for the BrowserAutomationProvider scaffold.

Ensures the typed boundaries raise NotImplementedError as expected
(the class is a scaffold with no implementation).
"""

from __future__ import annotations

import pytest

from argus.providers.browser_automation import BrowserAutomationProvider


def test_browser_automation_provider_scaffold_raises_not_implemented() -> None:
    """All three tier method sets raise NotImplementedError as expected."""
    provider = BrowserAutomationProvider()

    # Tier A: read-only
    with pytest.raises(NotImplementedError):
        provider.inspect_dom("body")
    with pytest.raises(NotImplementedError):
        provider.take_screenshot()
    with pytest.raises(NotImplementedError):
        provider.navigate("https://example.com")

    # Tier B: confirmed
    with pytest.raises(NotImplementedError):
        provider.click_element("button")
    with pytest.raises(NotImplementedError):
        provider.fill_field("input", "value")
    with pytest.raises(NotImplementedError):
        provider.submit_form("form")

    # Tier C: autonomous
    with pytest.raises(NotImplementedError):
        provider.submit_payment(10.0, "usd")
    with pytest.raises(NotImplementedError):
        provider.modify_account_settings("acct-1", {"theme": "dark"})
    with pytest.raises(NotImplementedError):
        provider.execute_autonomous_workflow({"action": "test"})  # type: ignore[arg-type]

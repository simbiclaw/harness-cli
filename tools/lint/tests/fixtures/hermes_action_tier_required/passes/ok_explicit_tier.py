"""ActionDescriptor with explicit tier — must pass."""

from argus.hermes.types import ActionDescriptor, ActionTier


def create_action() -> ActionDescriptor:
    return ActionDescriptor(
        tier=ActionTier.B,
        name="click_submit",
        target="#submit-btn",
    )

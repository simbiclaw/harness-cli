"""ActionDescriptor without tier — must fail."""

from argus.hermes.types import ActionDescriptor


def create_action() -> ActionDescriptor:
    return ActionDescriptor(
        name="click_submit",
        target="#submit-btn",
    )

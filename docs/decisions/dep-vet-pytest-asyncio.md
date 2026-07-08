# Dep-vet: pytest-asyncio

Decision: APPROVED
Date: 2026-05-01

## Metadata
Ecosystem: pypi
First published: 2016-01-01
Latest version: 1.4.x
License: Apache-2.0
Source: https://github.com/pytest-dev/pytest-asyncio

## Checks
Age:        PASS (>3000 days since first publish)
Downloads:  PASS (~10M/week)
Activity:   PASS (active commits within last 90 days)
License:    PASS (Apache-2.0)

## Rationale
pytest-asyncio enables async test support for Argus. The CLI makes async
calls to the Anthropic SDK and async IO operations; tests exercising these
paths require asyncio fixtures and event-loop management.

# Dep-vet: pydantic

Decision: APPROVED
Date: 2026-05-01

## Metadata
Ecosystem: pypi
First published: 2017-07-01
Latest version: 2.13.x
License: MIT
Source: https://github.com/pydantic/pydantic

## Checks
Age:        PASS (>3000 days since first publish)
Downloads:  PASS (~100M/week)
Activity:   PASS (active commits within last 90 days)
License:    PASS (MIT)

## Rationale
Pydantic is the data-validation and settings-management layer for Argus.
All domain types (FactCheckVerdict, ActionDescriptor, INTENTS read results)
use Pydantic models for validation and serialization.

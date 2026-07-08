# Dep-vet: python-dotenv

Decision: APPROVED
Date: 2026-05-01

## Metadata
Ecosystem: pypi
First published: 2014-01-01
Latest version: 1.2.x
License: BSD-3-Clause
Source: https://github.com/theskumar/python-dotenv

## Checks
Age:        PASS (>4000 days since first publish)
Downloads:  PASS (~20M/week)
Activity:   PASS (active commits within last 90 days)
License:    PASS (BSD-3-Clause)

## Rationale
python-dotenv loads environment variables from .env files for local
development. Required because the CLI reads API keys and configuration
from env vars at runtime per docs/conventions/deps-and-secrets.md.

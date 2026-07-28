---
name: dep-vetter
description: Vet a candidate Python dependency against the four-check policy
  (age, weekly downloads, recent commits, license). Invoked when the
  PreToolUse hook blocks a `uv add` or `pip install` with a "no dep-vet
  record" message, or invoked manually before adding a new dependency.
  Writes the result to `docs/decisions/dep-vet-<pkg>.md`.
---

# Dep-Vetter Skill

## When to use this skill

Before adding any direct dependency to `pyproject.toml`, or when the
PreToolUse hook blocks an install with a "no dep-vet record" message.

## Inputs

- `package`: the PyPI package name (e.g., `httpx`)

## Process

1. Fetch package metadata from PyPI: `https://pypi.org/pypi/<package>/json`
2. From the metadata, extract:
   - First-published date (earliest release in `releases`)
   - Latest version
   - License classifier
   - Source repo URL (from `info.project_urls.Source` or `info.home_page`)
3. Fetch weekly download stats:
   `https://pypistats.org/api/packages/<package>/recent?period=week`
4. Fetch the source repo's most recent commit. For GitHub:
   `https://api.github.com/repos/<owner>/<repo>/commits?per_page=1`
   For GitLab/Bitbucket, use the equivalent endpoints.
5. Verify the license string matches the allowed set (default: MIT, Apache-2.0,
   BSD-2-Clause, BSD-3-Clause, ISC, MPL-2.0, Unlicense). The full list lives
   in `docs/conventions/deps-and-secrets.md`.

## Decision rules

- Age: >30 days since first publish.
- Downloads: >1000/week (PyPI's `pypistats` recent-week count).
- Activity: most recent commit within 90 days.
- License: in the allowed set.

ALL must pass. Any single failure = REJECT.

## Output

Write `docs/decisions/dep-vet-<pkg>.md` with this structure:

```
# Dep-vet: <pkg>

Decision: APPROVED | REJECTED
Date: <YYYY-MM-DD>

## Metadata
Ecosystem: pypi
First published: <date>
Latest version: <version>
License: <SPDX ID>
Source: <URL>

## Checks
Age:        <PASS|FAIL> (<N> days since first publish)
Downloads:  <PASS|FAIL> (<N>/week)
Activity:   <PASS|FAIL> (last commit <N> days ago)
License:    <PASS|FAIL> (<SPDX ID>)

## Rationale
<one paragraph: why this dependency is needed; what alternatives were
 considered; why this one wins>

Source: <URL to PyPI page or repository>
```

## On REJECT

Do NOT proceed with the install. Open a section in the active ExecPlan
explaining the rejection and proposing alternatives. Wait for human
steering. Override only via commit message containing
`[dep-override-approved-by-human]` (audited by the doc-gardener).

Last reviewed: 2026-05-01

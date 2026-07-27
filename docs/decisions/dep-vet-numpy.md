# Dep-vet: numpy

Decision: APPROVED
Date: 2026-07-27

## Metadata
Ecosystem: pypi
First published: 2006-12-02
Latest version: 2.5.1
License: BSD-3-Clause
Source: https://github.com/numpy/numpy

## Checks
Age:        PASS (7168+ days since first publish)
Downloads:  PASS (>100,000,000/week — most downloaded Python package)
Activity:   PASS (last commit 1 day ago)
License:    PASS (BSD-3-Clause — in allowed set)

## Rationale
Required by the audio2tree skill pipeline (scripts/cluster.py) for:
- K-means clustering of request embeddings (numpy array operations)
- Centroid distance calculations for contrastive sample selection
- Embedding vector math

NumPy is the standard array library for Python. There is no viable alternative
for numerical computation at this scale. It is already a transitive dependency
of scikit-learn (used by the same pipeline) but is declared explicitly to
ensure availability.

Source: https://pypi.org/pypi/numpy/

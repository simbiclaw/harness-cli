# docs/decisions/

Records of repository-level decisions that are not tied to a single ExecPlan. Currently used for:

- **`dep-vet-<package>.md`** — output of the dep-vetter skill. One file per direct dependency in `pyproject.toml`.

ExecPlan-scoped decisions live in the **Decision Log** section of the relevant ExecPlan under `docs/plans/`, not here.

The structural test `.claude/tests/test_dep_decisions.py` walks this directory and asserts every direct dependency in `pyproject.toml` has a matching `dep-vet-<package>.md` file.

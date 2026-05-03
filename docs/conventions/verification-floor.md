# Verification Floor

No milestone is done until proof of behavior exists. For a CLI tool, proof means: the binary runs, exits with the expected code, and produces the expected output.

## Acceptance Test required per milestone

Every milestone in every ExecPlan has an `Acceptance Test:` line naming a specific runnable test (`tests/path/to/test.py::test_function_name`) that validates the milestone's externally observable property. The test is written first or in the same commit as the implementation. Untested milestones cannot have their checkbox flipped.

## Externally observable property

For a CLI tool, the canonical Acceptance Test invokes the CLI as a subprocess and asserts on the externally observable surface:

```python
import subprocess

def test_convert_handles_csv_input(tmp_path):
    input_file = tmp_path / "input.csv"
    input_file.write_text("a,b\n1,2\n")

    result = subprocess.run(
        ["uv", "run", "argus", "convert", str(input_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "1,2" in result.stdout
    assert result.stderr == ""
```

What counts as "externally observable" for a CLI:

- Exit code (`returncode`).
- Bytes on stdout (parseable by callers' shell scripts; this is a public contract).
- Bytes on stderr (informational, but format consistency still matters).
- Files written to disk under paths the CLI claims to write to.
- Side effects on resources the CLI claims to manage (a database, a remote API — see the next section).

What does *not* count as the sole acceptance criterion:

- "The function returns the expected dict." Internal-API tests are useful but cannot be the sole proof of milestone correctness; the CLI surface must be exercised.
- "Mock was called with these arguments." Mocks prove the inside, not the outside.
- "No exception was raised." Silent success is not proof.

## External integrations require recorded transcripts

If the CLI calls a third-party API, the Acceptance Test records the HTTP exchange (via `vcrpy`, `respx`, or `pytest-recording`) and commits the recording to `tests/cassettes/`. Live-network tests do not count toward the verification floor. The recorded fixture is treated as part of the test and reviewed on PR like any other test code.

## Test layout

```
tests/
├── unit/                    # Internal-API tests. Fast. Run on every change.
├── integration/             # Subprocess invocations. The verification floor.
│   └── cassettes/           # Recorded HTTP for tests that need network.
└── conftest.py
```

The Acceptance Test for a milestone almost always lives in `tests/integration/`. Unit tests are supplementary, not sufficient.

## Flakes are bugs, not nuisances

A flaky test does not pass for milestone purposes. The fix is a follow-up ExecPlan to stabilize it. Re-running CI does not flip the milestone checkbox. If a test is flaky because it depends on real time, real network, real filesystem race conditions, or random data, the test itself is wrong; fix the test.

## The Verifier subagent

When a Progress checkbox flips from `[ ]` to `[x]`, the Verifier subagent re-runs the named Acceptance Test in a clean checkout (using `uv run pytest <test-id>` against a fresh `uv sync`). On pass: writes "verified at SHA <sha>" to the Decision Log. On fail: reverts the checkbox flip and adds an entry to Surprises & Discoveries. See `.claude/skills/verifier/SKILL.md`.

Last reviewed: 2026-05-01.

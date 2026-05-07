# Verification Floor

No milestone is done until proof of behavior exists. Every milestone in every ExecPlan has an `Acceptance Test:` line naming a specific runnable test. The test is written first or in the same commit as the implementation. Untested milestones cannot have their checkbox flipped.

## Per-layer test floor

What "test-floor-met" means depends on the layer. The definitions below are the minimum; exceeding them is fine, falling short is not.

### Repo

Every Repo method has a test that **fails before implementation and passes after**. The test exercises the method's external contract: for a read method, assert on the returned shape and null-vs-data discrimination; for a write method, assert on the persisted state being retrievable and correct. Repo never throws on "not found" — returns a typed null-or-not result. Tests assert this.

### Service

Every Service function is exercised by a test that asserts on its **return type** and at least one **specific value transformation** (given known inputs, the output has this specific property). Service is pure with respect to I/O — functions take Types and return Types. Tests exercise that purity: no external calls, no side effects.

### Runtime

Every job has an integration test covering **one happy path and one failure path**. Happy path: the job completes and produces the expected output. Failure path: the job encounters a retryable failure, the retry policy fires, and the job either succeeds or surfaces the failure correctly (no silent hangs, no partial output).

### UI

Every interactive element has a **stable test selector** (data attribute, not CSS class or nth-child) and at least one **click-target test** that asserts the element responds to interaction. Stable selectors use `data-testid` or equivalent; implementation-detail selectors (CSS class, DOM position) are not stable.

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

What counts as "externally observable":

- Exit code (`returncode`).
- Bytes on stdout (parseable by callers; this is a public contract).
- Bytes on stderr (format consistency still matters).
- Files written to disk under paths the CLI claims to write to.
- Side effects on resources the CLI claims to manage.

What does *not* count as the sole acceptance criterion:

- "The function returns the expected dict." Internal-API tests are useful but cannot be the sole proof.
- "Mock was called with these arguments." Mocks prove the inside, not the outside.
- "No exception was raised." Silent success is not proof.

## External integrations require recorded transcripts

If the system calls a third-party API, the Acceptance Test records the exchange (via `vcrpy`, `respx`, or equivalent) and commits the recording to `tests/cassettes/`. Live-network tests do not count toward the verification floor. The recorded fixture is treated as part of the test and reviewed like any other test code.

## Test layout

```
tests/
├── unit/                    # Internal-API tests. Fast. Run on every change.
├── integration/             # Subprocess invocations. The verification floor.
│   └── cassettes/           # Recorded HTTP for tests that need network.
└── conftest.py
```

The Acceptance Test for a milestone almost always lives in `tests/integration/`.

## Flakes are bugs

A flaky test does not pass for milestone purposes. Re-running CI does not flip the milestone checkbox. If a test is flaky because it depends on real time, real network, real filesystem race conditions, or random data, the test itself is wrong; fix the test.

## The Verifier subagent

When a Progress checkbox flips from `[ ]` to `[x]`, the Verifier subagent re-runs the named Acceptance Test in a clean checkout. On pass: writes "verified at SHA \<sha\>" to the Decision Log. On fail: reverts the checkbox flip and adds an entry to Surprises & Discoveries. See `.claude/skills/verifier/SKILL.md`.

Last reviewed: 2026-05-07.

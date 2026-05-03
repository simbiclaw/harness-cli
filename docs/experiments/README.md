# docs/experiments/

Runnable experiments that ground Decision Log entries marked with the **Empirical** rationale shape. Each experiment is its own subdirectory:

```
docs/experiments/NNNN-<name>/
├── README.md       # Question, methodology, conclusion
├── run.sh          # Reproducible invocation
├── results/        # Captured output
└── analysis.md     # Optional summary
```

The README starts with a single sentence: *"This experiment tested whether X is true. The answer is: Y, with Z caveats."*

Experiments are committed to the repo so future ExecPlans can re-cite them. See `docs/conventions/i-dont-know-protocol.md` for the citation contract.

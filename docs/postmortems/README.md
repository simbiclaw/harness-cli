# docs/postmortems/

Incident write-ups for things that went wrong: production bugs, secret leaks, broken releases, harness failures. Each postmortem is a single Markdown file:

```
docs/postmortems/YYYY-MM-DD-<slug>.md
```

Recommended structure:

- **What happened** — facts, no blame.
- **Impact** — who/what was affected, for how long.
- **Root cause** — the thing that, if absent, would have prevented this.
- **Detection** — how we noticed.
- **Resolution** — what we did.
- **Lessons** — what we change going forward, framed as harness promotions where possible.

Postmortems feed the promotion ladder. A pattern that recurs across two postmortems is a candidate for promotion from documentation to a hook, structural test, or CI gate.

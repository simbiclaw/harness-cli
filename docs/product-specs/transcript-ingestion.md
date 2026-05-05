## Feature slug

transcript-ingestion

## User job

When a call ends, the QA reviewer wants to feed the transcript into the system so that scoring can begin.

## Acceptance behavior

The CLI accepts a file path (`-t`) or batch directory (`-b`) and produces a `CleanTranscript` object with verified speaker roles and noise flags. A transcript with unrecognized format exits with code 1 and a logged `ASR_PARSE_ERROR`.

## Tiebreaker citations

- Scoring accuracy vs. throughput — accuracy wins. The ingestion stage must not drop or misattribute turns to chase speed.

## Open questions

- Awaiting Steering: Which source ASR system generates the transcripts and in which format? The PRD shows three parsed formats but the integration point is undocumented.

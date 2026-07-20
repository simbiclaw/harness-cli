---
verification-status: proposed
last-reviewed: 2026-07-20
consumed-by: ConversationDistillation
---

# Audio Intake (shared)

## User job

Convert raw support-call recordings into **structural transcription** — text aligned with speaker, time, and acoustic features — that downstream Conversation Distillation can deconstruct into atomic claims. The user is the platform itself; there is no direct human user of this layer.

## Acceptance behaviour

Given a raw audio file (formats: at minimum WAV, MP3, FLAC), the system produces a structural transcription with the following observable properties:

- **Speaker-attributed**: each segment names a speaker via diarisation. Speaker labels are stable within a single call (speaker-1 stays speaker-1 throughout) and unstable across calls (no global speaker identity).
- **Time-aligned**: each segment carries a start and end timestamp accurate to 100ms or better.
- **Voice-activity gated**: silence and non-speech audio are excluded from segments; long silences are preserved as gap markers.
- **Acoustic-feature annotated**: each segment carries Acoustic Feature data (pitch contour, energy, spectral characteristics) referenced by the Acoustic Feature expertise module — this annotation is Argus-required and produced for every call regardless of which app consumes the transcription downstream.

A reviewer reading the structural transcription can reconstruct the call's turn-taking without listening to the audio. This is the test: if the transcription omits speaker boundaries or timing badly enough that the call is ambiguous from the text alone, the transcription has failed regardless of word-level accuracy.

## Pipeline shape

```
audio file → VAD (gate non-speech)
          → Diarisation (assign speakers)
          → ASR (transcribe each segment)
          → Acoustic Feature Extraction (parallel branch)
          → Structural Transcription (merged output)
```

The four stages are separable. Each is a Service in the AudioIntake domain; Runtime composes them. The acoustic-feature branch runs in parallel with ASR rather than after, because the feature extraction works on raw audio frames and does not need the transcribed text.

## Interfaces produced

`ITranscriptionStream` — declared in `AudioIntake/Types`, consumed by `ConversationDistillation` (see `ARCHITECTURE.md § 3` dependency matrix). The shape:

```
StructuralTranscription = {
  callId: CallId,
  durationMs: number,
  segments: Segment[],
  acousticProfile: AcousticProfile,
}
Segment = {
  speaker: SpeakerLabel,         // stable within call
  startMs: number,
  endMs: number,
  text: string,
  confidence: number,            // ASR confidence
  acousticFeatures: AcousticFeatures,
}
```

## Failure modes and tolerances

**ASR confidence below threshold on a segment**: keep the segment with a `low-confidence` flag; do not drop. Downstream Conversation Distillation decides how to handle low-confidence segments per its own contract.

**Diarisation collapses two speakers into one**: this corrupts every downstream signal. Detected by acoustic-feature inconsistency within a single labelled speaker (pitch range too wide). Triggers a `diarisation-suspect` flag on the entire transcription; downstream consumers are responsible for handling the flag.

**Audio quality too poor to transcribe**: emit an `untranscribable` transcription with the reason. Do not fail silently.

**Out-of-vocabulary domain terms**: ASR will mistranscribe domain-specific terminology (digital certificate names, government office names, regional terms). The Phrase&Keyword expertise module supplies a domain-specific lexicon that ASR uses for biasing; lexicon updates are a separate offline pipeline.

## Forbidden behaviours

This domain does not interpret content. It does not classify the call. It does not guess at intent. It produces structural transcription faithful to the audio; downstream domains interpret. Mixing transcription with interpretation here would invert the dependency direction in `ARCHITECTURE.md § 3`.

This domain does not retain audio after transcription completes. The audio file is the user's data; once the transcription is produced and stored, the audio reference may be retained for re-transcription if the upstream provider supports it, but no audio payload is kept by this domain. Retention policy for source audio is owned by the upstream call-recording system, not by this platform.

## Tiebreaker references

- `PRODUCT_SENSE.md § Cross-product` for the bottom-up-authority rule that this pipeline ultimately serves.
- `PRODUCT_SENSE.md § Argus` for the acoustic-feature requirement that mandates Acoustic Feature extraction for every call.

## Open questions

> **Question**: Is transcription real-time or batch? The `PRODUCT_SENSE.md § Argus` failure tolerance permits 24-hour latency, which suggests batch is acceptable; Hermes's procedural execution path may need real-time transcription if Hermes ever runs during a live support call rather than after.
> **Default if not decided**: batch, with an aspiration toward streaming for the Hermes use case marked `Confidence: low` `Revisit: 2026-08-01`.

> **Question**: What is the language scope? The PRDs imply Mandarin (the RegTech domains are PRC-specific) but do not say. Multilingual handling has architectural implications (multiple ASR providers, multiple lexicon layers).
> **Default if not decided**: single-language (Mandarin) at bootstrap; multi-language is an explicit non-goal until decided.

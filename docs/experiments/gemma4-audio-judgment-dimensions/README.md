# Gemma 4 audio: reliable perceptual-judgment dimensions beyond transcription

**Status: protocol designed, not yet executed.** This is a research brief and
falsifiable experiment design, not a completed empirical result — it does not
yet ground a Decision Log entry with the Empirical rationale shape. It becomes
one once the protocols below are run and `results/` is populated.

**Provenance / scope note.** This work is advisory input for a *successor*
ExecPlan, not part of `9021-relayer-argus-eval-pipeline`. 9021's Q21
("Is an MLX Provider in this plan's scope, or a successor's?") explicitly
scoped local-MLX-served proposer models — which includes evaluating
`gemma-4-E4B-it` and `gemma-4-12B` as candidate S2 proposer engines — to
"a successor plan's scope, owned by the proposer line." No such plan exists
yet, so this brief has no milestone to cite and is filed as ad-hoc research
(`Plan: docs/exec-plans/ad-hoc`). It should be attached to that successor
plan's Decision Log once one is opened.

**Setup under test.** `gemma-4-E4B-it` (bf16, dedicated audio encoder) and
`gemma-4-12B` Unified (8-bit), served locally via `mlx-vlm`, OpenAI-compatible
endpoint, audio as `input_audio` content (one audio per request; max 30s,
silent truncation). Official audio tasks per Google: ASR + speech translation.

**Already established (do not re-derive; carried over from the requester's
own prior testing, not reproduced here):** transcription is reliable
("second-transcriber" grade), robust to −35 dB volume and 120–320 wpm, and
produces empty output on silence/non-speech (usable as a speech-presence
detector). Every direct judgment query tested so far — speaker count,
enumeration, open description, speech-rate judgment, pause duration, yes/no
questions — is unreliable: hallucinates or self-contradicts against ground
truth and silence negatives, is phrasing-non-deterministic, and in one case
denied speech content existed on a clip it transcribed correctly.

**Discipline.** This model family produces confident, well-formed, fabricated
perceptual judgments. Every test below must be able to fail. Every protocol
distinguishes "the model perceives X from audio" from "the transcript leaked
X to a downstream text-only judgment" — the latter is not an aural capability
and is reported as a separate, labeled finding, never folded into a dimension's
result.

---

## A — Evidence research

**Architecture differs between the two served models — treat them as two
separate hypotheses, not one capability at two sizes.** Per the Gemma 4
Technical Report (Gemma Team, Google DeepMind, [arXiv:2607.02770](https://arxiv.org/abs/2607.02770)):

- **E4B**: a dedicated 305M-parameter USM-style Conformer audio encoder (two
  downsampling conv layers + twelve Conformer layers), 40ms mel-filterbank
  chunks, **frozen during pretraining** — the LLM ingests continuous encoder
  embeddings. 55% parameter cut from Gemma 3n's 680M audio encoder.
- **12B Unified**: encoder-free. Raw 40ms/16kHz audio chunks (640-dim vectors)
  are projected **directly** into the LLM embedding space with no positional
  encoding, trained end-to-end from scratch. No dedicated acoustic-feature
  stage exists at all.

**Official training/benchmarking is ASR + AST only — no exceptions found.**
Every audio benchmark the technical report cites is FLEURS (ASR) and CoVoST
(speech-to-text translation): relative improvements of 17%/12% (ASR) and
12%/10% (AST) for E2B/E4B over Gemma 3n. Zero benchmarked claims were found
for emotion, speaker gender/age, music-vs-speech, noise, or overlapping
speech in the primary source. Marketing copy claiming broader "audio
understanding" is not backed by a cited eval in anything reviewed — treat as
marketing, not benchmarked, until shown otherwise.

**One model-specific negative result exists.** A community DoRA fine-tune of
`gemma-4-e4b-it` on audio-QA data
([`bnovikov/gemma-4-e4b-audio-v3`](https://huggingface.co/bnovikov/gemma-4-e4b-audio-v3))
reports emotion-flip detection regressed **−15pp** vs. the base model after
fine-tuning, and temporal reasoning stayed **near-random (~10%)** in both
base and fine-tune, with an explicit recommendation to avoid the model for
emotion-change-over-time tasks. This concerns emotion *dynamics* on a
downstream fine-tune, not static valence on the base model under test here —
but it is the only model-specific, non-marketing signal found, and it is
negative.

**One encoder-probing result bears on speaker attributes.** A third-party
extraction of the E4B audio encoder
([`rnagabh/gemma4-audio-encoder`](https://huggingface.co/rnagabh/gemma4-audio-encoder))
reports the embedding space shows *some* speaker separation (cosine-similarity
gap ≈0.03) but states: "the model was not trained for speaker verification,
and dedicated speaker models will significantly outperform it on speaker
tasks." Same source: strong on acoustically distinct lexical content (F1 0.93
on "seven"), weaker on confusable pairs ("three"/"tree") — evidence about
phonetic discrimination, not judgment.

**No source addresses language ID, music/noise, or overlap directly**,
benchmarked or anecdotal, for Gemma 4. That is a genuine evidence gap, not a
negative finding — the ranking below treats it as "untested, high theoretical
prior," not "refuted."

**`mlx-vlm` setup is confirmed standard.** `mlx_vlm.server` exposes an
OpenAI-compatible `/v1/chat/completions` endpoint and accepts local audio
file paths; 8-bit MLX builds keep language-decoder linears at mxfp8 while
audio/vision projectors stay bf16 — the 12B-8bit configuration under test is
not degrading the audio path beyond what the model card implies.

**Access limitation, disclosed.** `ai.google.dev`, `huggingface.co`,
`blog.google`, and direct `arxiv.org` fetches were blocked by this
environment's network egress policy during research (confirmed via
`/root/.ccr/README.md`, not a transient failure). Findings above come from
web-search-tool result summaries plus one full-text read of the technical
report via alphaXiv's paper-content tool — the one primary source read in
full. The two Hugging Face community findings are single-source,
community-authored model cards, not peer-reviewed or Google-published —
treat as unverified claims pending this experiment's own results.

Sources:
- [Gemma 4 Technical Report (arXiv:2607.02770)](https://arxiv.org/abs/2607.02770)
- [bnovikov/gemma-4-e4b-audio-v3 (Hugging Face)](https://huggingface.co/bnovikov/gemma-4-e4b-audio-v3)
- [rnagabh/gemma4-audio-encoder (Hugging Face)](https://huggingface.co/rnagabh/gemma4-audio-encoder)
- [Introducing Gemma 4 12B: a unified, encoder-free multimodal model (Google blog)](https://blog.google/innovation-and-ai/technology/developers-tools/introducing-gemma-4-12b/)
- [Blaizzy/mlx-vlm (GitHub)](https://github.com/Blaizzy/mlx-vlm)

---

## B — Ranked dimension table and protocols

**Shared methodology, applies to every dimension below (stated once):**

- **Lexical-leakage control (mandatory):** every positive stimulus uses a
  *fixed carrier sentence* whose words carry zero information about the
  judged dimension (the RAVDESS/CREMA-D pattern: identical short neutral
  sentences spoken across all emotion/gender/effort conditions). For each
  dimension, also run the **downstream-text-model control**: transcribe with
  the already-validated ASR mode, then ask a *text-only* model (no audio) to
  make the same judgment from the transcript alone. Matching audio and
  text-only performance means the "judgment" is lexical leakage, not aural
  perception — report as a separate labeled finding, not as a capability.
- **Negative controls, every dimension:** silence, non-speech environmental
  sound (MUSAN noise/music), and a class-mismatched distractor (e.g. for
  language ID: a language outside the answer set; for emotion: a neutral
  clip). A confident, wrong, non-refusal answer on any negative control
  auto-rejects the dimension regardless of positive-set accuracy.
- **≥3 phrasing variants:** (a) closed-set forced choice with an explicit
  option list, (b) same list reordered, (c) a structurally different framing
  (e.g. "respond with only the code X/Y/Z"). Never open-ended "describe" or
  yes/no — both already shown unreliable.
- **Repeats:** every stimulus run twice at temperature 0; a flip between runs
  is an automatic fail for that item.
- **Acceptance criterion (shared floor):** ≥90% correct on the controlled
  positive set, consistent across all phrasing variants, zero fabricated
  (non-refusal) answers on any negative control, no flips across identical
  repeats. Failing the negative-control check auto-rejects the dimension
  regardless of positive accuracy.
- **Run E4B and 12B-Unified as separate rows per dimension** — do not average
  or assume transfer between them, given the architecture difference in
  Workstream A.

| Rank | Dimension | Theoretical basis | Corpora (synth + real) | Format | Dimension-specific negative control | Prior |
|---|---|---|---|---|---|---|
| 1 | **Spoken language ID** (closed-set) | Necessary latent sub-skill of AST, which is officially benchmarked and measurably improved (CoVoST +10–12% relative) — correct translation requires correct source-language resolution on nearly every covered-language input | Synth: multilingual TTS reading the same neutral sentence in 8–10 languages. Real: FLEURS or Common Voice clips (languages Gemma is evaluated on) | "Which language is spoken? Choose one: [en/es/fr/de/zh/ja/ar/hi]" | Non-covered language (e.g. Basque) should elicit "not in list"/refusal, not a confident wrong pick from the option set | High |
| 2 | **Speech / non-speech / music** (3-way forced choice) | ASR objective requires the encoder to gate speech-bearing regions; partial behavioral evidence already exists (empty transcript on silence/non-speech) — tests whether it generalizes to a direct query, not just the decoder's emergent behavior | Synth: pure tones, white noise. Real: MUSAN (purpose-built speech/music/noise split) | "Is this speech, music, or noise? Choose one." | Silence must not be forced into one of the three classes — must refuse/say "no audio content" | High |
| 3 | **Background-noise presence** (binary: clean vs. noisy) | Standard ASR pipelines train on noise-augmented data for robustness; unconfirmed specifically for Gemma 4 by any source found — untested prior, not refuted | Synth: LibriSpeech/FLEURS clips + MUSAN noise mixed at 0/10/20 dB SNR. Real: CHiME or VoxCeleb "in the wild" clips | "Is there background noise present? Yes/no, then state confidence." Binary only — do not ask noise *type*, enumeration-shaped and known-fragile | Silence and pure-noise-no-speech negatives must not both get "yes, noisy speech" | Moderate |
| 4 | **Overlapping speech presence** (binary: single- vs. multi-talker, not a count) | Overlap is a known WER-degradation condition, so the encoder plausibly has some implicit sensitivity — but the established speaker-count-hallucinates-on-silence finding is a direct negative precedent for anything count-shaped, so this must be presence-only | Synth: LibriMix-style 2-speaker mixes at varying SIR. Real: AMI meeting corpus segments | "Do you hear one speaker or more than one speaker overlapping? Choose one." | Single-speaker-with-background-music must not be misclassified as overlap — separate confound from the noise dimension | Moderate |
| 5 | **Vocal effort / whisper** (binary: normal vs. whispered) | No ASR training incentive either way (content-WER is nominally effort-invariant), but whispered speech has an unusually large spectral difference (aperiodic, no F0) even at mel-filterbank resolution — cheap test with genuine uncertainty | Synth: TTS whisper-style output if available; otherwise real-only. Real: wTIMIT or CHAINS (matched normal/whispered same-text pairs) | "Is this speech whispered or spoken normally? Choose one." | A quiet-but-voiced (low-volume, not whispered) clip must not be misclassified as whisper — isolates effort from volume, already shown robust to −35dB | Low–moderate |
| 6 | **Speaker gender** (binary, fixed carrier sentence) | Direct negative evidence exists (encoder-probe: "not trained for speaker verification," dedicated models outperform it) — but that is an embedding probe, not the instruction-tuned model's verbalized judgment, so it is suggestive, not dispositive | Synth: multi-voice TTS (known ground-truth voice metadata), same sentence. Real: VoxCeleb | "Is the speaker male or female? Choose one." | Gender-neutral/ambiguous synthetic voice should trigger a hedge, not a confident pick | Low |
| 7 | **Speaker age** (young/old binary) | Strictly harder than gender (finer acoustic cue, more confusable), no training signal, no evidence either direction — lowest-value use of budget in this family | Synth: age-varied TTS voices. Real: CREMA-D (has age metadata) | "Does the speaker sound young or old? Choose one." | Child voice vs. adult voice must be consistently distinguished, or auto-reject | Low |
| 8 | **Emotion valence/arousal** (forced choice: happy/sad/angry/neutral, fixed carrier sentence) | The one dimension with model-specific negative evidence already published (−15pp emotion-flip regression, ~10% near-random temporal reasoning on this exact model family) — must still be tested since it is the headline question, but ranked last because it is simultaneously the highest-interest and best-evidenced-to-fail dimension, and the most leak-prone (happy sentences often contain happy words) | Synth: emotion-conditioned TTS, same sentence across emotions. Real: RAVDESS (gold standard — actors say two fixed carrier sentences across 8 emotions, eliminating lexical leakage by construction) | "What emotion is being expressed: happy, sad, angry, or neutral?" | Neutral-content clip read in a flat tone across all four candidate emotions is the leak-detection stimulus — variation without emotional words present is real signal; no variation is the expected failure | Lowest (do not skip) |

---

## Recommended MVP experiment: Spoken Language ID

**Why this one, not speech/music/noise (rank 2) or emotion (the highest-interest
one):** language ID is the only dimension where a positive result would be
traceable to something already proven — AST accuracy Gemma 4 is officially
benchmarked and measurably improved on. A pass tells us the established
failure mode is "any judgment not literally required by the training
objective," not "any judgment at all" — the single most decision-relevant
fact for scoping every other row in this table, at near-zero marginal cost.

**Protocol.**

1. Pull 8 languages × 3 clips each (5–10s, neutral content) from FLEURS — a
   corpus Gemma 4 is already evaluated against, eliminating domain-mismatch
   risk from the result.
2. Negative controls: 3 silence clips, 3 non-speech (MUSAN noise/music), 3
   clips in a language *not* in the answer set (tests refusal behavior, not
   just accuracy on covered options).
3. Three phrasings: (a) "Which language is being spoken? Choose one: [list]."
   (b) same list, reordered. (c) "Respond with only the ISO 639-1 code, or
   'none' if you cannot determine it."
4. Corroboration probe: for each positive clip, separately prompt "Translate
   this to English," then ask "What source language did you translate from?"
   Check whether the trusted AST behavior and the explicit language-ID claim
   agree — disagreement is diagnostic even if raw accuracy looks fine.
5. Run every stimulus twice at temperature 0.
6. Score against the shared acceptance floor above: ≥90% on positives across
   all 3 phrasings, zero confident labels on silence/non-speech, correct
   refusal on non-covered languages, no repeat-flips.

Total stimulus count: 24 positive + 9 negative × 2 repeats × 3 phrasings ≈
200 calls per model — cheap, and the highest-information single run
available given what is already established.

## Next steps

- Execute the MVP protocol against both `gemma-4-E4B-it` and `gemma-4-12B`
  (8-bit), record raw outputs (including failures) under `results/`.
- If Rank 1 passes, proceed down the table in order; if it fails, treat that
  as evidence the failure mode is architectural/global, and downgrade the
  prior on every lower-ranked row before spending budget on them.
- Once a successor ExecPlan for the local-audio proposer line exists (per
  9021 Q21), fold this brief's outcome into its Decision Log with the
  Empirical rationale shape, citing this file and `results/`.

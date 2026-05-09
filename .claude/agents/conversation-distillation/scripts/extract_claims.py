"""
Claim extraction.

Two paths:

1. The inline path: the subagent's reasoning extracts claims directly from
   structural transcription JSON. This script's role on the inline path is
   only to provide the canonical prompt template (see EXTRACTION_PROMPT
   below) so that the inline extraction matches the batch extraction.

2. The batch path: this script reads structural transcription files and
   calls a configured LLM endpoint. Defaults to a local OpenAI-compatible
   endpoint at $OPENAI_API_BASE (typical: http://localhost:8000/v1 for
   vllm-mlx, llama.cpp's server, or LM Studio); falls back to Anthropic's
   API via $ANTHROPIC_API_KEY if local isn't reachable.

Both paths produce identical schema (see references/claim_schema.md) and
write to the same claim_library.jsonl.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Iterable

# Local imports
sys.path.insert(0, str(Path(__file__).resolve().parent))
from state_io import (  # noqa: E402
    append_claims, claim_library_path, log_event, load_processed,
    mark_processed,
)
from verify_claims import verify_claim  # noqa: E402


EXTRACTOR_VERSION = "conversation-distillation@1.0"

EXTRACTION_PROMPT = """\
You are extracting atomic claims from a single segment of a support call transcript. The transcript was produced by an upstream pipeline (structural-transcription); each segment has a speaker, a time interval, and ASR text.

Your job: from this one segment, produce zero or more atomic claims. Each claim is a single proposition.

The four non-negotiable gates every claim must satisfy:

1. SINGLE PROPOSITION. One logically complete and independent statement. If you can split into two claims and each stands alone, do.

2. DE-CONTEXTUALISED. Replace pronouns and underspecified phrases with specific entities. "It hasn't arrived" → "The U-Key driver order placed by the customer on the prior Tuesday has not arrived." If you cannot resolve a reference using the segment text plus the supplied neighbouring segments, drop the claim — do not invent a referent.

3. NOT A Q&A PAIR. A claim is a proposition, not an exchange. A customer's question becomes a claim about what the customer wanted to know. An agent's answer becomes a claim about what the agent asserted. Two claims, never one merged Q&A.

4. SOURCE-CITED. Every claim cites the segment IDs that ground it.

The five claim types (exhaustive — pick one; if none fits, drop the claim):
  - assertion: speaker stated a fact about the world or themselves
  - inquiry: speaker wanted to know something
  - commitment: speaker committed to do something
  - complaint: speaker expressed dissatisfaction with a specific event/state
  - preference: speaker stated a preferred option among alternatives

Filler turns (backchannels like "uh-huh", short acknowledgments under ~5 words, sign-offs) produce no claims. If the segment is filler, return an empty array.

If the speaker hedged ("may", "might", "I think"), preserve the hedge faithfully — don't strengthen or weaken it. If the segment doesn't actually contain a proposition (only fillers, hedging without content, pure social acknowledgment), return an empty array.

INPUT (you will receive these as JSON below):
- target_segment: the segment to extract from
- neighbouring_segments: segments before/after that may supply antecedents
- audio_id: the structural transcription's audio.id
- speaker_role: "customer", "agent", or "unknown"

OUTPUT (return as a JSON array, one object per claim, no other text):
[
  {{
    "claim_type": "assertion" | "inquiry" | "commitment" | "complaint" | "preference",
    "speaker_role": "customer" | "agent" | "unknown",
    "proposition": "...",
    "source": {{
      "audio_id": "...",
      "segment_ids": [<int>],
      "supporting_segment_ids": [<int>, ...]
    }},
    "decontextualisation": {{
      "resolved_references": [
        {{"surface": "it", "resolved_to": "..."}}
      ],
      "resolution_evidence_segment_ids": [<int>, ...]
    }}
  }}
]

If no claims warrant extraction, return [].

INPUT:
{input_json}

OUTPUT:
"""


# ---------------------------------------------------------------------------
# Claim ID generation
# ---------------------------------------------------------------------------


def _claim_id(claim: dict) -> str:
    """SHA-256 of canonical content (excludes id, created_at) → c_<12hex>."""
    payload = {
        "claim_type": claim.get("claim_type"),
        "speaker_role": claim.get("speaker_role"),
        "proposition": claim.get("proposition"),
        "source": claim.get("source"),
        "decontextualisation": claim.get("decontextualisation"),
        "extractor_version": EXTRACTOR_VERSION,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "c_" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _finalize_claim(c: dict, extraction_method: str) -> dict:
    """Add the system-managed fields and return a complete claim object."""
    out = {
        "schema_version": "1.0",
        "claim_type": c.get("claim_type"),
        "speaker_role": c.get("speaker_role"),
        "proposition": c.get("proposition", "").strip(),
        "source": c.get("source", {}),
        "decontextualisation": c.get("decontextualisation", {
            "resolved_references": [],
            "resolution_evidence_segment_ids": [],
        }),
        "extraction_method": extraction_method,
        "extractor_version": EXTRACTOR_VERSION,
        "supersedes": c.get("supersedes"),
    }
    # Ensure source has the optional supporting field
    if "supporting_segment_ids" not in out["source"]:
        out["source"]["supporting_segment_ids"] = []
    out["id"] = _claim_id(out)
    out["created_at"] = _now()
    return out


# ---------------------------------------------------------------------------
# LLM endpoint client (OpenAI-compatible chat/completions, streaming-free)
# ---------------------------------------------------------------------------


def _llm_call(prompt: str, model: str | None = None) -> str:
    """
    Call the configured LLM endpoint. Tries OpenAI-compatible first
    (typical local vllm-mlx setup), falls back to Anthropic API.
    """
    base = os.environ.get("OPENAI_API_BASE", "http://localhost:8000/v1")
    if _can_use_openai_compatible(base):
        return _openai_call(base, prompt, model or os.environ.get("CD_LLM_MODEL", "default"))
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _anthropic_call(prompt, model or "claude-sonnet-4-6")
    raise RuntimeError(
        "No LLM endpoint reachable. Set OPENAI_API_BASE to a running OpenAI-"
        "compatible server, or set ANTHROPIC_API_KEY."
    )


def _can_use_openai_compatible(base: str) -> bool:
    """Cheap reachability probe."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(base.rstrip("/") + "/models", method="GET")
        # Most OpenAI-compatible servers don't require auth for /models, but
        # tolerate a 401 — the endpoint exists, the auth might just be wrong.
        try:
            urllib.request.urlopen(req, timeout=2.0)
            return True
        except urllib.error.HTTPError as e:
            return e.code in (401, 403, 404)  # endpoint exists
        except urllib.error.URLError:
            return False
    except Exception:
        return False


def _openai_call(base: str, prompt: str, model: str) -> str:
    import urllib.request
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2000,
    }).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(
        base.rstrip("/") + "/chat/completions",
        data=body, headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


def _anthropic_call(prompt: str, model: str) -> str:
    import urllib.request
    api_key = os.environ["ANTHROPIC_API_KEY"]
    body = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body, headers=headers, method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    # Concatenate text content blocks
    parts = [b["text"] for b in data["content"] if b.get("type") == "text"]
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Per-segment extraction
# ---------------------------------------------------------------------------


def _neighbour_window(segments: list[dict], idx: int, window: int = 3) -> list[dict]:
    """Up to `window` segments before and after the target."""
    start = max(0, idx - window)
    end = min(len(segments), idx + window + 1)
    return [s for j, s in enumerate(segments[start:end]) if (start + j) != idx]


def _is_filler(text: str) -> bool:
    """Quick filler detection — short tokens, no propositional content."""
    t = (text or "").strip()
    if not t:
        return True
    word_count = len(t.split())
    if word_count <= 4:
        # Likely filler/backchannel/sign-off — but a 4-word turn could still
        # be a claim ("the order is missing"). Use heuristic: must contain
        # a verb-shaped token to count as content. Approximation: the text
        # contains at least one word of length ≥ 4 that isn't a conjunction
        # or pronoun.
        pure_filler = {"yeah", "yes", "no", "okay", "ok", "uh", "um", "mm", "mhm",
                       "thanks", "thank", "you", "right", "sure", "alright",
                       "great", "fine", "sorry", "huh", "wait", "hmm", "well", "ah", "oh"}
        words = {w.lower().strip(".,!?") for w in t.split()}
        if words.issubset(pure_filler):
            return True
    return False


def extract_claims_from_segment(
    segments: list[dict], idx: int, audio_id: str, speaker_role: str,
    extraction_method: str = "batch_script",
) -> list[dict]:
    """
    Extract claims from segments[idx] using its neighbours for context.
    Returns finalized claim objects (with id and created_at filled in).
    """
    target = segments[idx]
    text = target.get("text", "")
    if _is_filler(text):
        return []

    neighbours = _neighbour_window(segments, idx)
    input_payload = {
        "audio_id": audio_id,
        "speaker_role": speaker_role,
        "target_segment": {
            "id": target.get("id"),
            "speaker": target.get("speaker"),
            "start_sec": target.get("start_sec"),
            "end_sec": target.get("end_sec"),
            "text": text,
        },
        "neighbouring_segments": [
            {
                "id": n.get("id"),
                "speaker": n.get("speaker"),
                "start_sec": n.get("start_sec"),
                "end_sec": n.get("end_sec"),
                "text": n.get("text"),
            }
            for n in neighbours
        ],
    }

    prompt = EXTRACTION_PROMPT.format(input_json=json.dumps(input_payload, ensure_ascii=False, indent=2))
    raw = _llm_call(prompt)

    candidates = _parse_llm_json_array(raw)
    finalized: list[dict] = []
    for c in candidates:
        # Force the audio_id and target segment id to match what we asked
        # about — protects against the model hallucinating different IDs.
        if "source" not in c:
            c["source"] = {}
        c["source"]["audio_id"] = audio_id
        if not c["source"].get("segment_ids"):
            c["source"]["segment_ids"] = [target.get("id")]
        c["speaker_role"] = speaker_role
        finalized_claim = _finalize_claim(c, extraction_method=extraction_method)
        result = verify_claim(finalized_claim)
        if result.passed:
            finalized.append(finalized_claim)
        else:
            log_event(
                "extraction_rejected",
                claim_id_attempted=finalized_claim["id"],
                audio_id=audio_id,
                segment_id=target.get("id"),
                proposition_preview=finalized_claim.get("proposition", "")[:120],
                gate_failures=result.failures,
            )
    return finalized


def _parse_llm_json_array(raw: str) -> list[dict]:
    """
    LLMs sometimes wrap JSON in code fences or add prose before/after.
    Strip fences and find the first balanced `[ ... ]` span.
    """
    s = raw.strip()
    # Remove common fences
    for fence in ("```json", "```JSON", "```"):
        if s.startswith(fence):
            s = s[len(fence):].lstrip("\n").rstrip("`").rstrip()
    # Find array span
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        return json.loads(s[start:end + 1])
    except json.JSONDecodeError:
        return []


# ---------------------------------------------------------------------------
# Per-file orchestration
# ---------------------------------------------------------------------------


def role_for_speaker(speaker_id: str, speakers: list[dict]) -> str:
    for s in speakers:
        if s.get("id") == speaker_id:
            label = s.get("label")
            if label == "agent":
                return "agent"
            if label == "customer":
                return "customer"
            return "unknown"
    return "unknown"


def process_file(path: Path, force: bool = False) -> tuple[int, int, str]:
    """
    Process one structural transcription file. Returns (n_extracted, n_segments, audio_id).
    """
    with open(path, "r", encoding="utf-8") as f:
        doc = json.load(f)

    audio_id = doc.get("audio", {}).get("id")
    if not audio_id:
        raise ValueError(f"{path}: missing audio.id")

    if not force and audio_id in load_processed():
        print(f"  skipping {audio_id} (already processed; pass --force to override)", file=sys.stderr)
        return 0, 0, audio_id

    speakers = doc.get("speakers", [])
    segments = doc.get("segments", [])
    extracted: list[dict] = []
    n_processed = 0

    for idx, seg in enumerate(segments):
        speaker_id = seg.get("speaker")
        role = role_for_speaker(speaker_id, speakers)
        try:
            claims = extract_claims_from_segment(
                segments, idx, audio_id, role, extraction_method="batch_script",
            )
        except Exception as e:
            print(f"  segment {seg.get('id')} extraction failed: {e}", file=sys.stderr)
            continue
        extracted.extend(claims)
        n_processed += 1

    if extracted:
        n_written = append_claims(extracted)
    else:
        n_written = 0

    mark_processed([audio_id])
    log_event(
        "file_processed",
        audio_id=audio_id, file=str(path),
        segments_seen=len(segments), segments_processed=n_processed,
        claims_written=n_written,
    )
    return n_written, n_processed, audio_id


def main() -> int:
    p = argparse.ArgumentParser(description="Extract atomic claims from structural transcriptions.")
    p.add_argument("--input", "-i", required=True, type=Path,
                   help="A single .structural.json file, or a glob pattern, or a directory")
    p.add_argument("--force", action="store_true",
                   help="Re-process files whose audio_id is already in processed_audio_ids.txt")
    args = p.parse_args()

    # Resolve inputs
    if args.input.is_dir():
        files = sorted(args.input.glob("*.structural.json"))
    elif "*" in str(args.input):
        files = sorted(Path().glob(str(args.input)))
    else:
        files = [args.input]

    if not files:
        print(f"No matching input files for {args.input}", file=sys.stderr)
        return 1

    log_event("run_started", phase="extraction", file_count=len(files))

    total_extracted = 0
    total_segments = 0
    for f in files:
        if not f.exists():
            print(f"  WARNING: {f} does not exist", file=sys.stderr)
            continue
        print(f"  extracting from {f.name}...", file=sys.stderr)
        try:
            n_e, n_s, _ = process_file(f, force=args.force)
        except Exception as e:
            print(f"  ERROR processing {f}: {e}", file=sys.stderr)
            log_event("file_failed", file=str(f), error=str(e))
            continue
        total_extracted += n_e
        total_segments += n_s

    log_event(
        "run_completed",
        phase="extraction",
        files=len(files),
        claims_written=total_extracted,
        segments_seen=total_segments,
    )
    print(f"Wrote {total_extracted} claims from {total_segments} segments across {len(files)} files.")
    print(f"Library now at: {claim_library_path()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

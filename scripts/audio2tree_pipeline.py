"""audio2tree pipeline orchestration — S1: Request extraction.

Reads .structural.json files from an input directory,
extracts customer turns, builds extraction prompts,
and writes a result JSON for downstream stages (S2–S4).
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Allow direct execution from anywhere in the repo tree
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.request_extractor import build_extraction_prompt


def read_structural_json(filepath: str) -> list[dict]:
    """Read a .structural.json file and return a list of call records.

    Handles two formats:
    - A single call record (dict) with ``audio_id`` and ``turns``.
    - An array of call records (list), each with ``audio_id`` and ``turns``.
    """
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data
    return [data]


def extract_customer_turns(turns: list[dict]) -> list[dict]:
    """Extract turns where the speaker is the customer.

    Handles both:
    - Direct labels: ``"agent"`` / ``"customer"``
    - Structural-transcription IDs: ``"S0"`` / ``"S1"`` (resolved via speakers list)
    """
    # If turns have speaker IDs like "S0"/"S1", we need a speakers mapping.
    # The caller provides this via the full call record.
    return [t for t in turns if t.get("speaker") == "customer"]


def resolve_speaker_labels(
    turn: dict, speaker_map: dict[str, str]
) -> str | None:
    """Resolve a turn's speaker to a human label.

    Args:
        turn: A turn dict with a ``speaker`` field.
        speaker_map: Mapping from speaker ID (e.g. "S0") to label (e.g. "agent").

    Returns:
        The human-readable label, or the raw speaker value if no mapping exists.
    """
    raw = turn.get("speaker", "")
    if raw in speaker_map:
        return speaker_map[raw]
    return raw


def get_customer_turns_with_mapping(
    call: dict,
) -> tuple[list[dict], list[int]]:
    """Get customer turns and their indices from a call record.

    Args:
        call: A call dict that may have ``turns``, ``speakers``, and ``audio_id``.

    Returns:
        (customer_turns, source_segment_ids) where customer_turns are the
        turn dicts with human labels and source_segment_ids are the indices
        of those turns in the original ``turns`` array.
    """
    turns = call.get("turns", [])

    # Build a speaker-ID-to-label map if the structural-transcription format
    # is used (e.g. speakers=[{"id": "S0", "label": "agent"}])
    speaker_map: dict[str, str] = {}
    for sp in call.get("speakers", []):
        sid = sp.get("id", "")
        label = sp.get("label", "")
        if sid and label:
            speaker_map[sid] = label

    customer_turns: list[dict] = []
    source_ids: list[int] = []

    for idx, turn in enumerate(turns):
        label = resolve_speaker_labels(turn, speaker_map)
        if label == "customer":
            # Normalize the speaker field to "customer" for downstream use
            enriched = dict(turn)
            enriched["speaker"] = "customer"
            customer_turns.append(enriched)
            source_ids.append(idx)

    return customer_turns, source_ids


def process_call(call: dict) -> dict | None:
    """Process one call record: extract customer turns and build a prompt.

    Args:
        call: A call dict with ``audio_id`` and ``turns``.

    Returns:
        A result dict with ``audio_id``, ``request_text`` (None for M1),
        ``source_segment_ids``, and ``prompt``, or None if no customer turns.
    """
    audio_id = call.get("audio_id", call.get("audio", {}).get("id", "unknown"))
    customer_turns, source_ids = get_customer_turns_with_mapping(call)

    if not customer_turns:
        return None

    prompt = build_extraction_prompt(customer_turns)

    return {
        "audio_id": audio_id,
        "request_text": None,
        "source_segment_ids": source_ids,
        "prompt": prompt,
    }


def process_directory(input_dir: str) -> list[dict]:
    """Process all .structural.json files in a directory.

    Args:
        input_dir: Directory path containing .structural.json files.

    Returns:
        List of result dicts (one per call with customer turns).
    """
    results: list[dict] = []

    if not os.path.isdir(input_dir):
        print(f"Error: input directory not found: {input_dir}", file=sys.stderr)
        sys.exit(1)

    files = sorted(
        f for f in os.listdir(input_dir) if f.endswith(".structural.json")
    )

    if not files:
        print(
            f"Error: no .structural.json files found in {input_dir}",
            file=sys.stderr,
        )
        sys.exit(1)

    for filename in files:
        filepath = os.path.join(input_dir, filename)
        calls = read_structural_json(filepath)

        for call in calls:
            result = process_call(call)
            if result is not None:
                results.append(result)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="S1: Extract customer Requests from structural transcripts."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing .structural.json files",
    )
    parser.add_argument(
        "--output-file",
        default=None,
        help="Path to write the extracted Requests JSON "
        "(default: requests.json in input-dir)",
    )
    args = parser.parse_args()

    output_file = args.output_file or os.path.join(args.input_dir, "requests.json")

    results = process_directory(args.input_dir)
    print(
        f"Processed {len(results)} call(s) with customer turns.",
        file=sys.stderr,
    )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Wrote results to {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()

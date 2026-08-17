#!/usr/bin/env python3
"""B-E refinement executor for the rubric-compiler skill (9003 M8).

Executes the B-E authoring step against the LOCAL model endpoint
(docs/references/ds4-flash-GUIDE.md — LiteLLM at 192.168.3.55:4000, model
deepseek-v4-flash-local, OpenAI-compatible chat completions). Reads every node
under `--out/nodes/`, identifies the checkable-False fallback signals in the
fail+excellence lanes, and asks the local model to decompose the unmatched
standard clauses into observable signals.

HALT semantics: an unreachable endpoint, non-200 response, malformed
response, or invalid refined-signal shape exits 2 with a one-line error
naming the endpoint and leaves the node UNCHANGED — there is no fallback to
the session model. The model identity is recorded in every decision entry
(`{"step": "b-e-refine", "item": <id>, "model": <LOCAL_MODEL_NAME>, ...}`
appended to `--out/compile-decisions.jsonl`).

GAN repair round (max-3-rounds discipline): a response that parses as JSON
but fails shape validation (missing required field / bad type), or returns
empty/whitespace-only content (transient server behavior), is re-requested
with the failure fed back to the model — budget 2 retries, 3 attempts total.
After shape validation, the merged node runs through the M1 validator
(`argus.core.compiler.validator.validate_node`, same sys.path bootstrap as
the runner); AUTH-1-style findings are equally repairable feedback (the GAN
Evaluator→Generator closure). Non-empty unparseable content halts
immediately. Persistent failures halt (exit 2, node UNCHANGED); every repair
is recorded as a `{"step": "b-e-repair", ...}` decision entry alongside the
`b-e-refine` entry.

Stdlib only (`urllib`) plus the in-repo argus core for the Evaluator gate —
no new dependencies. The endpoint is env-overridable:
LOCAL_MODEL_URL (default http://192.168.3.55:4000), LOCAL_MODEL_NAME
(default deepseek-v4-flash-local), LOCAL_MODEL_API_KEY (default sk-1234, the LAN
deployment's dev token).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]  # scripts/ → rubric-compiler/ → skills/ → .claude/ → repo

# --- sys.path bootstrap (mirrors run_compile.py) ---------------------------
try:  # pragma: no cover
    import argus  # noqa: F401
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(REPO_ROOT / "src"))

try:
    from argus.core.compiler.validator import validate_node

    VALIDATOR_AVAILABLE = True
except ImportError:
    VALIDATOR_AVAILABLE = False

DEFAULT_URL = "http://192.168.3.55:4000"
DEFAULT_MODEL = "deepseek-v4-flash-local"
DEFAULT_API_KEY = "sk-1234"
REQUEST_TIMEOUT = 300  # seconds — the LAN model may take minutes for 16384 tokens
MAX_ATTEMPTS = 3  # GAN repair budget: 2 retries, 3 attempts total

# The B-E protocol (system message): one observable signal per fallback
# clause, no evaluative adjectives (AUTH-1), gate_checkable_test shape,
# strict JSON output.
B_E_PROTOCOL = (
    "You are the B-E refinement step of the 9003 soft-criteria rubric compiler. "
    "For every standard clause the deterministic compiler left as a checkable-False "
    "fallback signal, author ONE observable signal per clause. Rules: "
    "(1) id is a stable item-lane sequence (e.g. 18-F1, 18-E1); "
    "(2) description names an OBSERVABLE pattern — what a proposer could find in a "
    "transcript and what a gate could verify — never an evaluative adjective "
    "(混乱/死板/合理/empathetic etc.); "
    "(3) severity is major or minor; "
    "(4) decomposed_from quotes the exact pass/fail_standard clause the signal traces to; "
    "(5) gate_checkable_test is an object with proposer_can_find_span and gate_can_verify; "
    "(6) checkable is True only when a deterministic gate can verify the signal, else False; "
    "(7) audit_result is pass / split / model_only per the gate-checkability audit. "
    'Respond with ONLY a JSON object: {"fail": [...], "excellence": [...]}. '
    "No markdown fences, no commentary, no keys besides fail and excellence."
)

REQUIRED_FIELDS = (
    "id",
    "description",
    "severity",
    "decomposed_from",
    "gate_checkable_test",
    "checkable",
    "audit_result",
)


class BefineError(Exception):
    """One-line halt condition: connection failure, non-200, malformed
    response, or invalid signal shape. The node is left UNCHANGED."""


class RepairableError(BefineError):
    """A response that failed in a repairable way: the failure is fed back to
    the model and the request is retried within the attempt budget. Messages
    carry no endpoint URL so the feedback stays clean."""

    def __init__(self, message: str, feedback: str) -> None:
        super().__init__(message)
        self.feedback = feedback


class ShapeValidationError(RepairableError):
    """A refined-signal payload that parsed as JSON but failed shape
    validation (missing required field / bad type)."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            feedback=(
                "Your previous response was rejected: "
                + message
                + ". Re-emit the complete JSON with ALL seven fields per signal."
            ),
        )


class EmptyResponseError(RepairableError):
    """Empty/whitespace-only content — transient server behavior, repairable."""

    def __init__(self) -> None:
        super().__init__(
            "empty response",
            "Your previous response was empty. Re-emit the complete JSON.",
        )


class ValidatorError(RepairableError):
    """The M1 validator rejected the merged node (e.g. an AUTH-1 evaluative
    adjective without a concrete referent). Repairable — the finding is fed
    back and the request retried (GAN Evaluator→Generator closure)."""

    def __init__(self, finding: str) -> None:
        super().__init__(
            finding,
            feedback=(
                "Your previous response was rejected by the validator: "
                + finding
                + ". Re-emit the complete JSON with all seven fields per signal, "
                "descriptions observable without evaluative adjectives."
            ),
        )


# ──────────────────────────────────────────────────────────────────────────
# Local model client (stdlib urllib only — no proxy for the LAN device)
# ──────────────────────────────────────────────────────────────────────────


def call_local_model(payload: dict[str, Any], url: str, api_key: str) -> dict[str, Any]:
    """POST the OpenAI-compatible chat-completions request to the local model.

    Returns the parsed JSON body. Raises BefineError on connection failure,
    non-200 status, or an unparseable response body — the caller halts.
    """
    request = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    # No proxy: the endpoint is a LAN device (or a test loopback server), and
    # a configured http_proxy would hijack both.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=REQUEST_TIMEOUT) as response:
            status = response.status
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:200].strip()
        raise BefineError(
            f"LOCAL_MODEL {url} unreachable: HTTP {e.code}{': ' + detail if detail else ''}"
        ) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise BefineError(f"LOCAL_MODEL {url} unreachable: {e}") from e
    if status != 200:
        raise BefineError(f"LOCAL_MODEL {url} returned HTTP {status}")
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as e:
        raise BefineError(f"LOCAL_MODEL {url} returned a non-JSON response: {e}") from e
    if not isinstance(parsed, dict):
        raise BefineError(f"LOCAL_MODEL {url} returned a non-object JSON response")
    return parsed


def extract_content(body: dict[str, Any], url: str) -> str:
    """Read choices[0].message.content from the chat-completions body."""
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise BefineError(
            f"LOCAL_MODEL {url} returned a malformed response: no choices[0].message.content"
        ) from e
    if not isinstance(content, str):
        raise BefineError(
            f"LOCAL_MODEL {url} returned a malformed response: choices[0].message.content is not a string"
        )
    if not content.strip():
        # Empty/whitespace-only content is transient server behavior —
        # repairable: feed the notice back and retry within the budget.
        raise EmptyResponseError()
    return content


def _strip_markdown_fence(content: str) -> str:
    """Strip a ```json ... ``` (or bare ``` ... ```) markdown code fence
    wrapper if the content is fenced; anything else passes through unchanged,
    so a genuinely non-JSON payload still halts in parse_refinement."""
    text = content.strip()
    if not text.startswith("```"):
        return text
    body_start = text.find("\n")
    if body_start == -1:
        # No newline ("```json{...}```"): cut the opening fence token and the
        # closing fence at the JSON's first brace.
        if text.endswith("```"):
            first_brace = text.find("{")
            if first_brace != -1 and first_brace < len(text) - 3:
                return text[first_brace:-3].strip()
        return text
    closing = text.rfind("```")
    if closing <= body_start:
        return text
    return text[body_start + 1 : closing].strip()


def parse_refinement(content: str, url: str) -> dict[str, list[dict[str, Any]]]:
    """Parse and validate the refined-signal payload.

    The content must be a JSON object with "fail" and "excellence" list keys;
    every entry must carry id, description, severity, decomposed_from,
    gate_checkable_test, checkable, and audit_result. Unparseable content is
    a malformed response — halt. A parseable payload with the wrong shape is
    a ShapeValidationError — repairable via the GAN retry loop.
    """
    try:
        parsed = json.loads(_strip_markdown_fence(content))
    except json.JSONDecodeError as e:
        raise BefineError(
            f"LOCAL_MODEL {url} returned a malformed response: content is not JSON: {e}"
        ) from e
    if not isinstance(parsed, dict):
        raise ShapeValidationError("the response is not a JSON object")
    refined: dict[str, list[dict[str, Any]]] = {}
    for lane in ("fail", "excellence"):
        lane_list = parsed.get(lane)
        if not isinstance(lane_list, list):
            raise ShapeValidationError(f"missing required '{lane}' list")
        for index, entry in enumerate(lane_list):
            if not isinstance(entry, dict):
                raise ShapeValidationError(f"{lane}[{index}] is not an object")
            for field in REQUIRED_FIELDS:
                if field not in entry:
                    raise ShapeValidationError(f"{lane}[{index}] lacks required field '{field}'")
            if not isinstance(entry["id"], str) or not entry["id"].strip():
                raise ShapeValidationError(f"{lane}[{index}] id must be a non-empty string")
            if not isinstance(entry["description"], str) or not entry["description"].strip():
                raise ShapeValidationError(f"{lane}[{index}] description must be a non-empty string")
            if not isinstance(entry["severity"], str):
                raise ShapeValidationError(f"{lane}[{index}] severity must be a string")
            if not isinstance(entry["decomposed_from"], str):
                raise ShapeValidationError(f"{lane}[{index}] decomposed_from must be a string")
            if not isinstance(entry["gate_checkable_test"], dict):
                raise ShapeValidationError(f"{lane}[{index}] gate_checkable_test must be an object")
            if not isinstance(entry["checkable"], bool):
                raise ShapeValidationError(f"{lane}[{index}] checkable must be a boolean")
            if not isinstance(entry["audit_result"], str):
                raise ShapeValidationError(f"{lane}[{index}] audit_result must be a string")
        refined[lane] = lane_list
    return refined


# ──────────────────────────────────────────────────────────────────────────
# Prompt construction and per-node refinement
# ──────────────────────────────────────────────────────────────────────────


def build_payload(
    node: dict[str, Any], item_id: str, raw_item: dict[str, Any] | None, model_name: str
) -> dict[str, Any]:
    """Assemble the chat-completions body for one item.

    Deterministic knobs: temperature 0 (greedy — cross-session reproducible),
    think false plus the explicit `thinking: {"type": "disabled"}` form
    (belt-and-suspenders — the deployment may still emit reasoning_content
    with think false alone), max_tokens 16384 (thinking tokens must not
    truncate the JSON mid-string). The user message carries the
    item id/text/pass_standard/fail_standard, the deterministic signals, and
    the instruction to decompose every checkable-False clause into observable
    signals.
    """
    human = node.get("human_version") or {}
    criterion = node.get("machine_criterion") or {}
    text = str((raw_item or {}).get("text") or human.get("text") or "")
    pass_standard = str(
        (raw_item or {}).get("pass_standard") or criterion.get("description") or ""
    )
    fail_standard = str((raw_item or {}).get("fail_standard") or "")
    signals = json.dumps(node.get("signals") or {}, ensure_ascii=False)
    user = (
        f"Item {item_id}: {text}\n"
        f"pass_standard: {pass_standard}\n"
        f"fail_standard: {fail_standard}\n\n"
        "Deterministic signals already in the node:\n"
        + signals
        + "\n\n"
        "Decompose every checkable: False fallback signal above into observable signals in its "
        "lane (fail/excellence). The checkable: True signals stay untouched. "
        'Return ONLY a JSON object: {"fail": [...], "excellence": [...]} with the refined '
        "signals for both lanes."
    )
    return {
        "model": model_name,
        "messages": [
            {"role": "system", "content": B_E_PROTOCOL},
            {"role": "user", "content": user},
        ],
        "temperature": 0,
        "think": False,
        "thinking": {"type": "disabled"},
        "max_tokens": 16384,
    }


def merge_refined(
    node: dict[str, Any],
    refined: dict[str, list[dict[str, Any]]],
    targets: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """A copy of the node with the refined signals merged into the targeted
    lanes (checkable-True signals kept, refined signals appended in order).
    The caller's node is never mutated — the write happens only after the
    full repair loop succeeds (HALT = UNCHANGED)."""
    merged = dict(node)
    merged["signals"] = dict(node["signals"])
    for lane in ("fail", "excellence"):
        if not targets[lane]:
            continue
        lane_signals = node["signals"][lane]
        merged["signals"][lane] = [s for s in lane_signals if s.get("checkable")] + refined[lane]
    return merged


def refine_node(
    path: Path,
    out: Path,
    url: str,
    api_key: str,
    model_name: str,
    plan_items: dict[str, dict[str, Any]],
) -> int:
    """Refine one node: replace checkable-False fallback signals with the
    local model's observable signals, append the decision entry, rewrite the
    node. Any halt condition leaves the node byte-identical (UNCHANGED)."""
    try:
        node = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read node {path.name}: {e}", file=sys.stderr)
        return 2
    if not isinstance(node, dict):
        print(f"error: node {path.name} is not a JSON object", file=sys.stderr)
        return 2
    signals = node.setdefault("signals", {})
    if not isinstance(signals, dict):
        print(f"error: node {path.name} has a malformed 'signals' field", file=sys.stderr)
        return 2

    item_id = path.stem.removeprefix("item-")
    targets: dict[str, list[dict[str, Any]]] = {}
    for lane in ("fail", "excellence"):
        lane_signals = signals.get(lane)
        if not isinstance(lane_signals, list):
            print(f"error: node {path.name} has a malformed 'signals.{lane}' field", file=sys.stderr)
            return 2
        targets[lane] = [s for s in lane_signals if not s.get("checkable")]
    if not targets["fail"] and not targets["excellence"]:
        print(f"item {item_id}: no checkable-False fallback signals — nothing to refine")
        return 0

    # GAN repair round: wrap call → parse → validate → M1-validate in a retry
    # loop (budget 2 retries, 3 attempts). A shape-validation failure, empty
    # content, or validator finding feeds the exact error back to the model
    # and retries; anything else halts immediately.
    if not VALIDATOR_AVAILABLE:
        raise BefineError(
            "M6a Requires: M5 — argus.core.compiler.validator is not importable; "
            "the Evaluator gate cannot run (no B-E refinement without the quality gate)"
        )
    payload = build_payload(node, item_id, plan_items.get(item_id), model_name)
    last_error: str | None = None
    refined: dict[str, list[dict[str, Any]]] | None = None
    candidate: dict[str, Any] | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            body = call_local_model(payload, url, api_key)
            content = extract_content(body, url)
            parsed = parse_refinement(content, url)
            merged = merge_refined(node, parsed, targets)
            validator_findings = validate_node(merged)
            if validator_findings:
                raise ValidatorError(validator_findings[0])
            refined = parsed
            candidate = merged
            break
        except RepairableError as e:
            last_error = str(e)
            if attempt == MAX_ATTEMPTS:
                raise BefineError(
                    f"LOCAL_MODEL {url} returned invalid refined signals after "
                    f"{MAX_ATTEMPTS} attempts: {last_error}"
                ) from e
            user = payload["messages"][1]
            user["content"] = str(user["content"]) + "\n\n" + e.feedback
    if refined is None or candidate is None:
        # Budget exhaustion raised inside the loop — unreachable.
        raise BefineError("internal error: refinement loop exited without a result")
    repairs = attempt - 1

    replaced = sum(len(refined[lane]) for lane in ("fail", "excellence") if targets[lane])
    # Only a fully successful refinement writes the node (HALT = UNCHANGED).
    path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False))

    with (out / "compile-decisions.jsonl").open("a", encoding="utf-8") as fh:
        if repairs:
            fh.write(
                json.dumps(
                    {
                        "step": "b-e-repair",
                        "item": item_id,
                        "model": model_name,
                        "rationale": f"{last_error} — retried",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        fh.write(
            json.dumps(
                {
                    "step": "b-e-refine",
                    "item": item_id,
                    "model": model_name,
                    "rationale": (
                        f"B-E refinement: {replaced} checkable-False fallback clause(s) "
                        "decomposed into observable signals via the local model"
                    ),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    note = f" (after {repairs} repair round(s))" if repairs else ""
    print(f"item {item_id}: B-E refined {replaced} checkable-False signal(s) via {model_name}{note}")
    return 0


# ──────────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="B-E refinement executor (9003 M8): decompose checkable-False "
        "fallback signals into observable signals via the LOCAL model"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="compile output dir (holds nodes/, compile-plan.json, compile-decisions.jsonl)",
    )
    args = parser.parse_args()

    url = os.environ.get("LOCAL_MODEL_URL", DEFAULT_URL)
    model_name = os.environ.get("LOCAL_MODEL_NAME", DEFAULT_MODEL)
    api_key = os.environ.get("LOCAL_MODEL_API_KEY", DEFAULT_API_KEY)

    nodes_dir = args.out / "nodes"
    if not nodes_dir.is_dir():
        print(f"error: no nodes dir at {nodes_dir} — run run_compile.py loop first", file=sys.stderr)
        return 2
    paths = sorted(nodes_dir.glob("item-*.json"))
    if not paths:
        print(f"error: no item-*.json nodes under {nodes_dir}", file=sys.stderr)
        return 2

    # Raw items (id → item dict) come from the run's plan; they supply the
    # pass/fail standards for the prompt. Optional — a node alone still works.
    plan_items: dict[str, dict[str, Any]] = {}
    plan_file = args.out / "compile-plan.json"
    if plan_file.is_file():
        try:
            plan = json.loads(plan_file.read_text())
            if isinstance(plan, dict):
                plan_items = {
                    it["id"]: it for it in plan.get("items", []) if isinstance(it, dict)
                }
        except (OSError, json.JSONDecodeError, TypeError, KeyError):
            plan_items = {}

    for path in paths:
        try:
            rc = refine_node(path, args.out, url, api_key, model_name, plan_items)
        except BefineError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())

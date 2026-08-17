# Muse Glimmer 30B — Client Interaction Guide (via llmlite :4000)

**Model:** Muse Glimmer-30B (Meta Superintelligence Lab, Apache 2.0, Aug 2026)
**Backend:** ExecuTorch MLX (Apple Silicon) + DFlash speculative decoding
**Access point:** `http://192.168.3.55:4000` (LiteLLM proxy) → ExecuTorch worker on `:8082`
**Model ID:** `muse-glimmer-30B`
**Auth:** `Authorization: Bearer sk-1234`

This guide is compiled from the official model card, the ExecuTorch Muse Glimmer
README, and verified behavior of this deployment. It tells a client how to get
the best out of the model through the LiteLLM gateway.

---

## 1. What this model is

Muse Glimmer is a ~30B-parameter dense causal transformer, quantized to ~4-bit
(K-quant, <20 GB) and optimized for **on-device agentic work**:

- **Agentic tasks** — multi-step planning, sequential tool invocation, failure
  recovery, long-horizon execution
- **Coding agents** — SWE-Bench-style workflows
- **Tool use / function calling** — reliable schema-based invocation
- **Multimodal reasoning** — screenshots, charts, documents, images
- **LLM-as-a-judge**, synthetic data generation

It ships with a **DFlash drafter** — a small block-diffusion model that proposes
blocks of tokens; the main model verifies them in parallel. Output quality is
identical to non-speculative decoding; only the speed changes. In this
deployment DFlash is active (measured ~36 tok/s decode, ~170 tok/s prefill on
M3 Ultra — vs ~26 tok/s without it).

**Out of scope:** audio input/output is not supported. The model may produce
inaccurate or biased content; in agentic contexts that take real-world actions,
use guardrails (human-in-the-loop for irreversible actions).

---

## 2. Endpoint, auth, and capabilities

| Item | Value |
|---|---|
| Base URL | `http://192.168.3.55:4000` (LiteLLM) |
| API | OpenAI-compatible `POST /v1/chat/completions` |
| Auth header | `Authorization: Bearer sk-1234` |
| Model ID | `muse-glimmer-30B` |
| Context window | **131,072 tokens** (128K) |
| Max output tokens | No hard server ceiling; **use ≤ 32,768** (official recommendation) |
| Capabilities | Chat ✅ Vision ✅ Tool calling (ATEM) ✅ |
| Streaming | Supported (`stream: true`) |

> Note: `/v1/responses` does **not** exist on this backend (404 is expected).
> Use `/v1/chat/completions` only.

Smoke test:

```sh
curl http://192.168.3.55:4000/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk-1234' \
  -d '{"model":"muse-glimmer-30B",
       "messages":[{"role":"user","content":"What is the capital of France?"}],
       "max_tokens":64,"temperature":0}'
```

---

## 3. The single most important knob: reasoning strength

Muse Glimmer is a **reasoning model**. It thinks privately first (the `to=self`
channel) and only then writes the visible answer (the `to=user` channel). The
amount of thinking is controlled by **reasoning strength**, officially defined
in the system prompt as `Reasoning strength: <value>`.

**Official levels:** `low` / `medium` / `high` / `xhigh`

- `high` / `xhigh` → use for **complex problem solving, coding, and agentic
  tasks** (official recommendation)
- `low` / `medium` → fast, short-reasoning chat

**How to set it through this server** (two equivalent ways):

```sh
# Option A — chat_template_kwargs (recommended for this backend)
curl http://192.168.3.55:4000/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sk-1234' \
  -d '{"model":"muse-glimmer-30B",
       "messages":[{"role":"user","content":"Solve this differential equation: ..."}],
       "max_tokens":4096,
       "chat_template_kwargs":{"reasoning_strength":"high"}}'

# Option B — system prompt (works identically)
# "messages":[{"role":"system","content":"Reasoning strength: high."}, ...]
```

> The template default is `high` when nothing is given.

### The empty-answer trap (critical)

The server extracts the `to=self` channel into `reasoning_content` and the
`to=user` channel into `content`. **If `max_tokens` runs out while the model is
still reasoning, `content` comes back empty** (`finish_reason: length`) even
though decoding was healthy. Verified behavior:

| reasoning_strength | Prompt | max_tokens | Visible content |
|---|---|---|---|
| high (default) | "2+2?" | 512 | ✅ "4" |
| high (default) | water cycle | 1024 | ✅ 595 chars |
| high (default) | CS essay | 1500 | ❌ empty (reasoning ran over budget) |
| low | CS essay | 512 | ✅ 1952 chars |

**Rule of thumb:** with `high`/`xhigh`, budget **≥ 8,192 tokens** (the model can
reason for thousands of tokens before answering). With `low`, 512–2048 is
usually enough. When you need a guaranteed visible answer under a tight budget,
use `low` or `medium`.

### Reading the reasoning

If the server is configured with `return_reasoning` (upstream `--tool-parser`
mode may vary), the private reasoning comes back as `reasoning_content` on the
message. Otherwise reasoning is discarded and only the visible answer is
returned. Clients that want the chain-of-thought for agentic debugging should
set `chat_template_kwargs: {"return_reasoning": true}`.

---

## 4. Sampling parameters (official best practices)

The model card recommends:

| Parameter | Recommended | Notes |
|---|---|---|
| `temperature` | **1.0** | default; 0.0 = greedy (deterministic) |
| `top_p` | **0.95** | nucleus sampling |
| `top_k` | **64** | top-k truncation |

- For **deterministic / reproducible** behavior (tests, evals, agent replay):
  `temperature: 0`.
- `reasoning_effort` is **rejected with 400** on this backend — use
  `chat_template_kwargs.reasoning_strength` instead.
- `developer` role is not supported by the template — use `system` role.

---

## 5. Tool calling (ATEM)

Tool calling is enabled (server runs `--tool-parser atem`). The canonical HF
chat template renders tool definitions, and the server converts Muse Glimmer's
native ATEM output into OpenAI-compatible `tool_calls`.

**Standard OpenAI tool schema** — pass tools exactly as you would to any
OpenAI-compatible endpoint:

```sh
curl http://192.168.3.55:4000/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sk-1234' \
  -d '{
    "model": "muse-glimmer-30B",
    "messages": [{"role": "user", "content": "What is the weather in Paris? Use the get_weather tool."}],
    "max_tokens": 1024,
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "Get current weather for a city",
        "parameters": {
          "type": "object",
          "properties": {"city": {"type": "string"}},
          "required": ["city"]
        }
      }
    }],
    "tool_choice": "auto",
    "chat_template_kwargs": {"reasoning_strength": "high"}
  }'
```

**Verified response shape:**

```json
{
  "choices": [{
    "message": {
      "tool_calls": [{
        "id": "call-...",
        "type": "function",
        "function": {"name": "get_weather", "arguments": "{\"city\": \"Paris\"}"}
      }]
    },
    "finish_reason": "tool_calls"
  }]
}
```

**Multi-turn agent loop** (the pattern this model is built for):

1. Send user request + tools → receive `tool_calls`
2. Execute the tool, append the result as a `tool` role message
   (`tool_call_id` = the call id from step 1)
3. Send the conversation back — the model diagnoses results, retries on
   failure, and continues until it emits a final answer (`finish_reason: stop`)

The template renders tool results via `<tool_output name="...">` and supports
tool namespaces (`ns.func`). Keep schema descriptions precise — ATEM argument
parsing is regex-based and scalar parameters are not whitespace-stripped.

---

## 6. Vision (images)

The served PTE is the **text-image** build. Use the OpenAI multimodal content
format:

```json
{
  "model": "muse-glimmer-30B",
  "messages": [{
    "role": "user",
    "content": [
      {"type": "text", "text": "Describe this screenshot and list the UI elements."},
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<b64>"}}
    ]
  }],
  "max_tokens": 2048,
  "chat_template_kwargs": {"reasoning_strength": "medium"}
}
```

- Base64 data-URLs are the reliable path through the LiteLLM proxy.
- Up to **4,096 visual tokens per image** (official spec).
- Works for screenshots, charts, and documents — the model's main multimodal
  use cases.

---

## 7. Context, sessions, and limits

- **Context window:** 131,072 tokens. Keep `prompt + output ≤ 131072`.
- **Max output:** the official integration uses 32,768; there is no hard server
  ceiling, but stay within the context window.
- **Session affinity:** per-conversation sessions are supported upstream
  (`session_id`), but this deployment serves a single session slot — send the
  full conversation history in `messages` for multi-turn continuity.
- **Prefix reuse:** a `reused_prompt_tokens` stat confirms the engine caches
  prefill — keep message prefixes stable across turns of the same conversation
  to get the cache hit.

---

## 8. Performance expectations

Measured on Apple M3 Ultra (this deployment, DFlash active):

| Metric | Value |
|---|---|
| Decode | ~33–36 tok/s |
| Prefill | ~170 tok/s |
| First-token latency | prompt-length dependent; short prompts ~1–2 s |

DFlash block diffusion proposes 16-token blocks; acceptance is highest on
greedy decoding. Sampling (temp 1.0) lowers acceptance — if raw speed is the
goal, use greedy.

---

## 9. Quick reference checklist

| Goal | Do this |
|---|---|
| Plain chat | `temperature: 0.0` (or 1.0 per official), `max_tokens` 1024+, no kwargs |
| Fast answers | `chat_template_kwargs: {"reasoning_strength": "low"}` |
| Complex/agentic tasks | `{"reasoning_strength": "high"}` + `max_tokens ≥ 8192` |
| Deterministic output | `temperature: 0` |
| Tool calls | standard OpenAI `tools` + `tool_choice: "auto"` (ATEM parser active) |
| Images | `content` array with base64 `image_url` |
| Chain-of-thought | `chat_template_kwargs: {"return_reasoning": true}` → `reasoning_content` |
| Long context | keep ≤ 131,072 total; stable prefixes for prefill reuse |
| `reasoning_effort` param | don't send — 400. Use `reasoning_strength` |

## 10. Pitfalls

1. **Empty `content` with `finish_reason: length`** — reasoning ran over the
   token budget. Raise `max_tokens` or lower reasoning strength.
2. **`/v1/responses` → 404** — not implemented; use `/v1/chat/completions`.
3. **`reasoning_effort` → 400** — unsupported; use `reasoning_strength`.
4. **`developer` role silently dropped** — the template has no developer turn;
   use `system`.
5. **Tool arguments not stripped** — ATEM parsing is regex-based; pass
   well-formed JSON, avoid whitespace-sensitive edge cases.
6. **Audio** — not supported (text + image only).
7. **Auth** — all requests need `Authorization: Bearer sk-1234`.

---

*Sources: Meta Muse Glimmer model card (modelscope.cn/meta-models/Muse-Glimmer-30B),
ExecuTorch muse-glimmer README (pytorch/executorch), and verified behavior of
this deployment (Aug 2026).*

# DeepSeek V4 Flash — Client Interaction Guide (via llmlite :4000)

**Model:** DeepSeek V4 Flash (DeepSeek, 0731 revision, chat-v2)
**Engine:** DwarfStar 4 (`ds4-server`, Metal on Apple Silicon)
**Access point:** `http://192.168.3.55:4000` (LiteLLM proxy) → ds4-server on `:8000`
**Model ID:** `deepseek-v4-flash-local`
**Auth:** `Authorization: Bearer sk-1234`

This guide is compiled from the DwarfStar 4 README, server help, and verified
behavior of this deployment. It tells a client how to get the best out of
DeepSeek V4 Flash through the LiteLLM gateway.

---

## 1. What this model is

DeepSeek V4 Flash is a **284B-parameter mixture-of-experts** model (≈37B active
per token):

- **43 layers**, 256 routed experts per layer, **6 active per token** + 1 shared
  expert
- **MLA attention with KV compression** (compressor/indexer layers) — this is
  what makes **1M-token context** practical on local hardware
- **Compressed KV cache** — small enough to be a first-class disk citizen
  (sessions survive restarts via disk KV checkpoints)
- This deployment: **Q4_K routed experts**, Q8_0 attention/shared/output, F16
  hyper-connections — asymmetric quantization tuned per tensor family
- **DSpark speculative decoding** is active in this deployment (greedy only)

**Engine personality:** built for **long agent sessions** — live KV reuse across
turns, prefix caching for stateless clients, exact tool-call replay.

---

## 2. Endpoint, auth, and capabilities

| Item | Value |
|---|---|
| Base URL | `http://192.168.3.55:4000` (LiteLLM) |
| Auth header | `Authorization: Bearer sk-1234` |
| Model ID | `deepseek-v4-flash-local` |
| Context window | **1,000,000 tokens** (1M) |
| Max output tokens | **393,216** (384K) when client omits a limit |
| APIs | OpenAI chat, OpenAI Responses, Anthropic messages, completions |
| Capabilities | Chat ✅ Thinking ✅ Tools ✅ Streaming ✅ |

The LOCAL deployment id is `deepseek-v4-flash-local` (verified in the proxy's
`/v1/models` list). `deepseek-v4-flash` is not present — the earlier alias
claim is stale; never request the bare `deepseek-v4-flash` id (cloud-routing
risk).

Smoke test:

```sh
curl http://192.168.3.55:4000/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sk-1234' \
  -d '{"model":"deepseek-v4-flash-local",
       "messages":[{"role":"user","content":"Say hello."}],
       "max_tokens":256,"think":false}'
```

---

## 3. Thinking mode — the model's defining behavior

DeepSeek V4 Flash is a **thinking model**. Requests **default to high-effort
thinking**; reasoning is streamed in the native API shape (`reasoning_content`
on chat, `response.reasoning` events on Responses), never mixed into final
text.

**Controls:**

| Want | Send |
|---|---|
| Non-thinking (fast, direct) | `"think": false` — or `"thinking": {"type": "disabled"}` — or `"model": "deepseek-chat"` |
| Default thinking (high) | omit the controls |
| **Think Max** (deepest reasoning) | `"reasoning_effort": "max"` (or `output_config.effort: max`) |
| Low/medium effort | `"reasoning_effort": "low"` / `"medium"` |

> Think Max requires `--ctx ≥ 393216`. This deployment runs **1M context**,
> so Think Max is fully available.

**Sampling in thinking mode (important):** like the official DeepSeek API,
knobs the request *omits* are fixed by the engine (see §4) — but **explicitly
set parameters always win**. A `temperature: 0` request is greedy through the
whole reasoning phase, giving deterministic thinking-mode output (this is how
benchmark harnesses and DSpark should run).

---

## 4. Sampling parameters

**Server defaults** (when a request omits a knob):

| Parameter | Default | Meaning |
|---|---|---|
| `temperature` | 1.0 | — |
| `top_p` | 1.0 | — |
| `min_p` | **0.05** | relative-probability filter (not nucleus mass) |

Recommended usage:

- **Deterministic / reproducible** (evals, agents, DSpark): `temperature: 0`
- **Creative chat**: `temperature: 1.0` or 0.8 with `top_p: 0.95`
- `seed`, `top_k`, `min_p` are all accepted

---

## 5. DSpark speculative decoding (active in this deployment)

DSpark is DeepSeek's auxiliary draft model: it reads main-model hidden states
and proposes up to **five future tokens**; the engine verifies with the main
model and commits the accepted prefix. The main model stays authoritative.

**Rules for clients:**

1. **Greedy only** — DSpark engages with `temperature: 0`. Sampled requests
   fall back to ordinary decoding and lose the speedup.
2. **Code benefits most**; predictable continuations see the largest gains.
   Low-yield prompts can be no faster or even slower.
3. **Not free**: it does not accelerate prefill, and adds its own weights to
   memory.
4. **Reproducibility caveat**: accepted blocks commit batched-verifier state,
   so a long greedy DSpark run may diverge byte-wise from one-token decode.
   This is not lower precision — for byte-for-byte reproducibility the
   upstream server supports `--dspark-strict` (not enabled here; greedy
   decoding itself is deterministic run-to-run).

**Measured in this deployment:** ~35-39 t/s decode with DSpark + greedy,
including thinking-mode overhead (vs ~24 t/s without).

---

## 6. Tool calling (DSML)

Tool schemas (OpenAI `tools` / `tool_choice`) are rendered into DeepSeek's
native **DSML tool format**; generated DSML calls are mapped back to
OpenAI-compatible `tool_calls` (or Anthropic `tool_use` blocks).

```sh
curl http://192.168.3.55:4000/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'Authorization: Bearer sk-1234' \
  -d '{
    "model": "deepseek-v4-flash-local",
    "messages": [{"role": "user", "content": "What is the weather in Paris? Use the get_weather tool."}],
    "max_tokens": 2048,
    "think": false,
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
    "tool_choice": "auto"
  }'
```

**How it works under the hood (and why it matters to you):**

- **Exact replay**: every tool call gets an unguessable API tool ID; the server
  remembers `tool id → exact sampled DSML block`. When the client sends that
  tool ID back on the next turn, the *exact* bytes the model sampled are
  replayed — keeping the rendered prompt byte-identical to the live KV
  checkpoint. **Always echo the `tool_call.id` you received** in the `tool`
  role message; never reformat tool calls yourself.
- **Canonicalization backup**: if exact replay is impossible, the server
  deterministically re-renders and, if needed, rewrites the live checkpoint or
  falls back to an older disk KV snapshot and replays only the suffix. Your
  transcript stays aligned.
- **Greedy protocol syntax**: while the model emits DSML structure (tags,
  headers, JSON punctuation), sampling is forced to `temperature: 0` so calls
  stay parseable — but **argument payloads** (`string=true` bodies, file
  contents, JSON string values) use your normal sampling settings, avoiding
  repetitive text in long code bodies.
- Streaming streams tool calls as soon as the DSML invocation is recognized:
  header first, then argument bytes as `tool_calls[].function.arguments`
  deltas.

**Multi-turn agent loop:**

1. Send request + tools → get `tool_calls` + ids
2. Execute, append `{"role": "tool", "tool_call_id": "<echo the id>", "content": ...}`
3. Repeat until `finish_reason: "stop"` with a final answer

---

## 7. Long conversations and KV cache

The server keeps **one live backend/KV checkpoint**. Stateless clients that
resend a *longer* version of the same prompt reuse the shared prefix instead of
pre-filling from token zero.

**Client rules for long sessions:**

- Keep message **prefixes stable** — append, don't rewrite. Prefix reuse is
  what makes 1M-token conversations practical.
- The full context window is 1M tokens; the KV cache is compressed and can be
  persisted to disk between server restarts.
- Tool-call turns are the fragile part — exact replay (echoing tool IDs) keeps
  the checkpoint aligned (§6).

---

## 8. Endpoint notes by client type

| Client | Endpoint | Notes |
|---|---|---|
| OpenAI-style | `/v1/chat/completions` | `messages`, `tools`, `temperature`, `seed`, streaming |
| **Codex CLI** | `/v1/responses` | Preferred for Codex; full Responses event lifecycle (`response.output_text.delta`, `response.completed`) |
| Claude Code style | `/v1/messages` | Anthropic shape: `system`, `tools`, `tool_use` blocks, thinking controls |
| Raw completions | `/v1/completions` | Legacy |

All endpoints support SSE streaming. In thinking mode, reasoning streams in the
native shape per endpoint.

---

## 9. Performance expectations

Measured on Apple M3 Ultra, this deployment (DSpark active, 1M ctx):

| Metric | Value |
|---|---|
| Decode (greedy + DSpark) | ~35-39 t/s |
| Decode (sampled, no DSpark) | ~24-28 t/s |
| Prefill | ~350-450 t/s |
| Context | 1M tokens |

Thinking mode adds reasoning tokens before the final answer — visible-answer
latency is dominated by reasoning length, not engine speed. Use `think: false`
for low-latency direct answers.

---

## 10. Quick reference checklist

| Goal | Do this |
|---|---|
| Plain chat | `"think": false`, `max_tokens` 1024+ |
| Deep reasoning | omit think controls, or `reasoning_effort: "max"` (Think Max, 1M ctx OK) |
| Deterministic output | `temperature: 0` |
| DSpark speed | `temperature: 0` (greedy) — code-heavy prompts benefit most |
| Tool calls | OpenAI `tools` + echo `tool_call.id` back verbatim |
| Long conversation | keep message prefixes stable; append only |
| Codex | `/v1/responses` endpoint |
| Claude Code | `/v1/messages` (Anthropic shape) |
| Reasoning text | read `reasoning_content` (chat) / reasoning events (Responses) |

## 11. Pitfalls

1. **Sampling knobs silently ignored in thinking mode** — unless set
   explicitly. If your request seems to ignore `temperature`, you are in
   thinking mode with the engine's fixed defaults; set the knob explicitly.
2. **DSpark only engages greedy** — sampled requests lose the ~40% speedup.
3. **Don't reformat tool calls** — always echo the received `tool_call.id`;
   exact DSML replay keeps KV prefix reuse working.
4. **Think Max needs ctx ≥ 393,216** — fine here (1M), but requests asking
   for `reasoning_effort: max` against a smaller context silently degrade to
   high.
5. **DSpark divergence** — a long greedy DSpark run may differ byte-wise from
   non-speculative decoding (same graph, different float grouping). Use
   `--dspark-strict` upstream if byte-reproducibility is mandatory.
6. **Model alias confusion** — `deepseek-v4-flash-local` and `deepseek-v4-pro` both
   serve the single loaded model.
7. **Reasoning is not final text** — reading only `content` while thinking is
   enabled can look like a stalled request; read `reasoning_content` too.

---

*Sources: DwarfStar 4 README (github.com/antirez/ds4), `ds4-server --help`,
DeepSeek DSML encoding docs, and verified behavior of this deployment
(Aug 2026).*

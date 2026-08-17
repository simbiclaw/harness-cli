# 9008 — Audio2Tree Rebuild: Real Audio to INTENTS, From Scratch

## 1. Purpose

本计划**完全取代并推翻** 9004（`docs/exec-plans/archived/9004-skill-prototype-cli-production.md`，已归档）。

**推翻原因：**

原计划的执行方案（两阶段：Claude-in-the-loop skill 原型 + Python 确定性脚本）在验收验证中暴露根本缺陷——S0（ASR）从未对真实 WAV 运行，S1（Claude 提取 Request）从未被调用（硬编码字符串顶替），S3 路由是空壳（`batch_route()` 将所有请求送进 deviation 通道），M4 验收从未达标即被勾选、同日撤回。缺陷是结构性的（验收基于 fixture 而非真实数据路径），无法通过局部修正解决，必须重新设计。

**与旧计划的关键区别：**

| 方面 | 原计划 (9004) | 本计划 (9008) |
|:-----|:--------------|:--------------|
| 输入 | fixture JSON / 手工转写 `.txt` | 5 个真实 WAV，S0 ASR 必跑 |
| S1 Request 提取 | 硬编码字符串顶替 Claude | Claude 从真实 ASR transcript 提取 |
| S3 路由 | `batch_route()` 空壳，全部 deviation | 真实 bge-m3 嵌入 + cosine 匹配 + 碰撞检测 |
| 验收标准 | 46 单元测试 = "端到端通过" | 每个里程碑在真实音频上运行（M0-M4 逐级） |
| 代码位置 | `scripts/` 项目根（后移至 skill） | `.claude/skills/audio2tree/scripts/` 全新编写 |
| 代码继承 | — | 不继承 `feat/audio2tree-skill` 分支任何代码 |

**Replacement plan:** 9008-audio2tree-rebuild

`Source: docs/exec-plans/archived/9004-skill-prototype-cli-production.md (Outcomes & Retrospective) · docs/retrospectives/9004-execution-mistakes.md · docs/references/audio2tree-pipeline-design.md · docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design.md`

## 2. Big Picture

The pipeline: **S0** ASR via the existing `structural-transcription` skill (WAV → `.structural.json`); **S1** Claude extracts one Request per call (one Chinese sentence, 8–80 chars) from the real ASR transcripts; **S2** embed Requests via local Ollama `bge-m3` (1024-d), k-means cluster, Claude names clusters with contrastive prompts (5 in-cluster + 5 contrastive samples); **S3** dual-channel routing — cosine match each Request against L2 description anchors from `intent_manifest.json` files (S_max ≥ 0.60 → matched; < 0.60 → deviation), collision detection freezes near-duplicate anchors (cosine > 0.7), deviation rate reported on stdout; **S4** write `intent_manifest.json → bottom_up` for L2/L3 nodes, never touching `top_down`.

All scripts are new and live in `.claude/skills/audio2tree/scripts/` per the Claude Code skills specification (9004 Mistake 3). The `structural-transcription` skill is reused as-is (S0). Design reference documents from 9004 remain valid inputs — the overturn invalidates the *execution plan*, not the product spec.

**Deliberately out of scope:**
- CLI surface (`argus audio2tree`) — Phase B concern, not built here
- Pipeline state persistence, stability protocol, neighborhood hierarchy — Phase B
- Criteria-shaped facets — 9003 companion territory
- Inheriting any code from `feat/audio2tree-skill` — overturn decision

**File Scope:**
- `.claude/skills/audio2tree/**` (new — skill, SKILL.md, scripts)
- `tests/test_audio2tree_*.py` (new — one test file per milestone)
- `INTENTS/**` (modify — bottom_up manifest output only; never `top_down`)
- `docs/retrospectives/9004-execution-mistakes.md` (read only)
- `docs/references/audio2tree-pipeline-design.md` (read only)
- `docs/exec-plans/active/9008-audio2tree-rebuild.md` (modify — this plan)

## 3. Milestones

### M0 — S0: ASR on 5 real WAV files

Run the existing structural-transcription pipeline on the 5 real WAV files at `/Users/prometheus/workspace/best-practice/3audio-engineering/origin_calls/1.wav` through `5.wav`, producing 5 `.structural.json` files. Requires `audio-server` (or the CLI backend) running.

`Acceptance Test:` `tests/test_audio2tree_s0.py::test_five_structural_json_produced` — for each of the 5 WAVs, a `.structural.json` exists, parses as JSON, has `schema_version`, `audio.id`, `speakers[]`, and non-empty `turns[]` with `text`.

### M1 — S1: Claude extracts one Request per call

Claude reads each real `.structural.json`, filters customer turns, and writes one Request per call: one Chinese sentence, 8–80 chars, no agent dialogue markers, mapping to its `audio_id`. Extraction prompt built by `build_extraction_prompt()` (new, in skill scripts); output validated by `parse_request_response()`.

`Acceptance Test:` `tests/test_audio2tree_s1.py::test_requests_from_real_transcripts` — the 5 Requests are produced **from the real ASR transcripts of M0** (assert each Request's source text appears in its transcript), each passes `parse_request_response` (8–80 chars, no agent markers, non-null), and each maps to a real `audio_id`.

### M2 — S2: Embedding + clustering + contrastive naming

Embed the 5 Requests via Ollama `bge-m3` at `localhost:11434` (1024-d). K-means with silhouette-optimal k (min 2). Claude names each cluster via contrastive prompt (5 in-cluster + 5 contrastive samples from nearest neighboring cluster). Names validated non-generic (not 其他咨询, 综合问题, 其他, 其他业务).

`Acceptance Test:` `tests/test_audio2tree_s2.py::test_real_requests_cluster_and_name` — ≥2 non-empty clusters from the 5 real Requests; every cluster has a name passing `validate_cluster_name()`; naming prompt has both `<同类 Request>` and `<对比 Request>` sections.

### M3 — S3: Dual-channel routing with real embeddings

Embed each Request and each L2 description anchor (from existing `intent_manifest.json` files, per `INTENTS/AGENTS.md` protocol) via Ollama `bge-m3`. Cosine-match: S_max ≥ 0.60 → matched channel; < 0.60 → deviation pool. Pairwise collision detection on L2 anchors (cosine > 0.7 freezes the newer anchor). Deviation rate = |D_deviation| / |D_total| reported on stdout.

`Acceptance Test:` `tests/test_audio2tree_s3.py::test_real_routing_reports_deviation_rate` — routing runs on the real 5 Requests with real Ollama embeddings (not mocks), produces per-request channel assignments, and prints deviation rate on stdout; if L2 anchors exist, matched channel is exercised.

### M4 — S4: Manifest population + end-to-end gate

Write `intent_manifest.json → bottom_up` for all L2/L3 nodes produced by M2+M3, merging into existing manifests without touching `top_down`. Wire M0→M1→M2→M3→M4 into one skill invocation (`/audio2tree cluster --input-dir <transcripts> --l1 法人数字证书业务`). This is the Phase A gate.

`Acceptance Test:` `tests/test_audio2tree_s4.py::test_full_pipeline_real_audio` — full S0→S4 run on the 5 real WAVs: exit 0; at least one `intent_manifest.json` under `INTENTS/` has a populated `bottom_up` (channel, request_count > 0, cluster_centroid 1024-d, representative_requests non-empty); all cluster names non-generic Chinese; `top_down` untouched; deviation rate on stdout; every manifest has `last_updated_by == "audio_to_tree"`.

## 4. Progress

- [ ] M0: S0 — ASR on 5 real WAV files  (created 2026-08-12)
- [ ] M1: S1 — Claude extracts one Request per call  (created 2026-08-12)
- [ ] M2: S2 — Embedding + clustering + contrastive naming  (created 2026-08-12)
- [ ] M3: S3 — Dual-channel routing with real embeddings  (created 2026-08-12)
- [ ] M4: S4 — Manifest population + end-to-end gate  (created 2026-08-12)

## 5. Decision Log

### Decision: Completely overturn 9004 and rebuild from scratch

**Rationale:** `Source: docs/exec-plans/archived/9004-skill-prototype-cli-production.md (Outcomes & Retrospective) · docs/retrospectives/9004-execution-mistakes.md` — 9004's Phase A gate was never met: S0/S1 never ran on real data, S3 routing was a no-op, and M4 was checked off then reverted on the same day. The failure was structural (the execution plan validated fixtures, not the pipeline), so it cannot be fixed by patching milestones. This plan replaces 9004 entirely. `Confidence: high`.

### Decision: Inherit none of the feat/audio2tree-skill execution code

**Rationale:** `Source: Structured interview 2026-08-12` — the overturn is complete ("从头再来"). The abandoned branch's code (`98e9ab8`…`db33dd4`) is treated as a failed attempt, not a baseline. All skill scripts and tests are written fresh in `.claude/skills/audio2tree/scripts/`, and every milestone's acceptance test runs on real audio. `Confidence: high`.

### Decision: Design reference documents remain valid inputs

**Rationale:** `Source: docs/references/audio2tree-pipeline-design.md · docs/superpowers/specs/2026-07-19-clio-to-audio2tree-design.md` — the overturn invalidates the 9004 *execution plan* (milestones, phases, acceptance), not the product spec (WHAT: dual-channel routing, contrastive naming, manifest schema §5, thresholds 0.60/0.70). The manifest JSON shapes and routing thresholds are adopted as-is from the design reference. `Confidence: high`.

### Decision: numpy dependency carried over from 9004

**Rationale:** `Source: docs/exec-plans/archived/9004-skill-prototype-cli-production.md (Decision Log 2026-07-27)` — `numpy>=2.0` already sits in main's `pyproject.toml` with a recorded rationale (k-means array operations, cosine). Rebuilding from scratch does not require removing it; it is required by the clustering stage. `Confidence: high`.

## 6. Surprises & Discoveries

*None yet — this section grows during execution. 9004's failure modes are documented in `docs/retrospectives/9004-execution-mistakes.md`; the expectation is that this rebuild surfaces new surprises, not the same ones.*

## 7. Awaiting Steering

> **No open questions at creation.** The overturn decision (complete rebuild, no code inheritance) was resolved by the human on 2026-08-12. Open questions discovered during execution are added here.

## 8. Outcomes & Retrospective

*Written at completion or cancellation.*

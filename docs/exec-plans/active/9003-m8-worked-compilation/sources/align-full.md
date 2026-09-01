# Alignment: Human QA Rubric → Generic Evaluator Skill Dimensions

This document maps the 25 operational items of `rubric_com_hotline.md`
(items 6 and 7 excluded — they require external system access) onto the
four dimensions of the evaluator-criteria skill. The 27 human QA items
are specific, observable behaviors. The four dimensions are independent
failure axes. Each item lands on the axis whose failure mode it primarily
detects.

---

## Excluded Items

| Item | Reason |
|------|--------|
| 6 (*) 服务记录规范 — ticket fields, filing within 5 min | Requires access to the ticketing system to verify timestamps and field correctness |
| 7 (*) 问题升级流程操作完整且规范 — escalation confirmation | Requires access to escalation records to verify submitted information |

Once system access is available, both are fully compilable: item 6 is a
`lookup` (ticket.fields ⊇ required_set, timestamp within 300s of call
end), item 7 is a `lookup` (escalation.fields ⊇ {qq, company_name,
issue_detail, callback_time}). Both at confidence 1.0.

---

## Dimension 1: Procedural Accuracy (weight: 2×)

**What it measures:** Whether the agent followed correct process —
script compliance, operational norms, information handling. These are
mostly structural, checkable behaviors.

| Item | Rubric entry | Why this axis |
|------|-------------|--------------|
| 1 | 有起接语且完整/外呼明确身份 | Script compliance — greeting is a structural check |
| 2 | 有称谓语且规范 | Script compliance — title usage, consistency, correctness |
| 3 | 能够快速准确灵活的进行信息查询及搜索 | Operational norm — query method correctness |
| 4 | 无声电话、保留电话、转接候线用语规范操作正确，候线时长不超过30秒 | Operational norm — hold/transfer procedure and duration |
| 5 | 有结束语且完整 | Script compliance — closing script is a structural check |
| 27 | 保证用户信息受到保护，不私自泄漏或公布用户隐私 | Compliance — information handling boundaries |

**Compilability:**

| Item | Compilable to | Confidence | Residue |
|------|--------------|-----------|---------|
| 1 | `lexical`: greeting phrase present in first agent turn | 1.0 | None |
| 2 | `lexical`: title used; `ordered_relation`: title consistent across turns | 1.0 | "礼貌地称呼，不引起反感" — tone-appropriateness of title |
| 3 | `lookup`: query method matches KB-prescribed method for issue type | 0.9 | "灵活运用不同方式进行搜索" — flexibility judgment |
| 4 | `threshold`: hold_duration < 30s; `lexical`: hold_phrase + recall_phrase present | 1.0 | None |
| 5 | `lexical`: closing_phrase present, "还有其他问题" check present | 1.0 | None |
| 27 | `lexical`: phone_number_pattern NOT IN transcript OR preceded_by verification | 1.0 | None |

---

## Dimension 2: Empathy & Tone (weight: 3×)

**What it measures:** Whether the agent acknowledged the customer's
emotional state and maintained a professional, warm communication
atmosphere. This is where the scripted-vs-genuine blind spot lives —
the highest-cost false positive in the evaluator's judgment.

| Item | Rubric entry | Why this axis |
|------|-------------|--------------|
| 8 | 表达清晰流畅，口齿清楚；无过多口语 | Communication quality — "口齿含糊不清", filler-word overuse |
| 10 | 适时使用礼貌用语 | Communication quality — "您" vs "你", politeness appropriateness |
| 11 | 语气亲切友善，体现热情，耐心的服务 | Core attitude — "爱理不理", "急于挂断", "冷漠、机械化" |
| 12 | 无无故打断客户的话或抢话、压话 | Listening attitude — interruption and conversational dominance |
| 13 | 集中精力倾听用户问题 | Listening attitude — "答非所问", "服务断片" |
| 14 | 表达委婉，善于使用正面言辞 | Communication style — "我不知道", "我没办法", "这个无法告诉您" |
| 22 | 情绪用户和潜在情绪（如抱怨等）处理 | Core empathy — "表现出同理心，采取认同、道歉、陈述等手段" |
| 26 (primary) | 沟通氛围融洽 — 讽刺、冷笑、不文明用语 | Attitude synthesis — detectable red flags |

**Compilability:**

| Item | Compilable to | Confidence | Residue |
|------|--------------|-----------|---------|
| 8 | `lexical`: filler_word_count("的话", "那个", "的哦") ≤ 2 | 0.85 | "口齿含糊不清", "体现专业性" — acoustic + semantic |
| 10 | `lexical`: "您" count vs "你" count ratio | 0.7 | "适时" — appropriateness is context-dependent |
| 11 | `acoustic`: prosody_warmth > threshold | 0.7 | "微笑服务", "敷衍" — warmth partially proxyable |
| 12 | `ordered_relation`: agent_speech ∩ customer_speech = ∅ | 0.9 | "适当礼貌的打断" — legitimate interruption needs context |
| 13 | `threshold`: agent_response_gap < τ after customer_speaks | 0.5 | "答非所问" requires full semantic understanding |
| 14 | `lexical`: banned_deflection_phrases ∩ transcript = ∅ | 0.8 | "说话生硬、唐突", "不合时宜的发笑" — subjective |
| 22 | `ordered_relation`: acknowledgment_span PRECEDES resolution_span | 0.6 | "表现出同理心", "有效引导情绪" — the core blind spot |
| 26 | `lexical`: banned_abuse_phrases ∩ transcript = ∅ | 0.6 | "隐藏的不满", "警觉性" — requires deep semantic understanding |

**The scripted-vs-genuine blind spot (items 11, 22):** An agent who says
"很抱歉给您带来不便" checks the lexical box but may be completely
insincere. The LLM evaluator must be calibrated against the specific
templated phrases used in this call center so it can distinguish "said
the word" from "meant the acknowledgment."

---

## Dimension 3: Problem Resolution (weight: 3×, hard threshold: 7)

**What it measures:** Whether the customer's actual problem was solved —
correctly, efficiently, and without creating additional work or future
issues. This is the functionality-equivalent gate.

| Item | Rubric entry | Why this axis |
|------|-------------|--------------|
| 16 | 理解用户的问题或需求 | Resolution prerequisite — misidentification ⇒ entire path is wrong |
| 17 | 能主动引导用户，有效把握电话节奏，保持客服引导与用户操作同步，无放空白过多或过长影响沟通氛围 | Resolution process — pace control, dead-air avoidance |
| 18 | 思路清晰，能根据客户理解程度，灵活的给予合理的处理办法，解释说明和操作指导 | Resolution quality — adaptability to customer's capability |
| 19 | 产品业务、操作知识把握准确 | Resolution foundation — incorrect knowledge ⇒ incorrect solution |
| 23 | 推卸自身工作职责，将本身工作范围内的问题，推诿给无关方 | Resolution ownership — deflecting = refusing to resolve |
| 24 | 方案准确性；在用户提供的现有信息下，提供给用户的方案准确 | Resolution verification — solution correctness and effectiveness |
| 25 | 业务办理引导准确，费用正确且办理资料无遗漏 | Resolution follow-through — business handling is the next step |

**Compilability:**

| Item | Compilable to | Confidence | Residue |
|------|--------------|-----------|---------|
| 16 | Not directly compilable | — | "辨识过程比较曲折" — detectable only through downstream patterns |
| 17 | `threshold`: silence (non-agent > 30s, agent-caused > 15s) | 0.8 | "被客户主导", "不关注客户理解程度" |
| 18 | `lookup`: solution matches KB for issue_type — partial proxy | 0.5 | "灵活" and "死板" — entirely context-dependent |
| 19 | `lookup`: agent_claimed_fact == KB.entry @ version | 1.0 | KB completeness is the bottleneck, not compilability |
| 23 | Not directly compilable | — | "推诿" vs "correct escalation" — intent-dependent |
| 24 | Partially proxyable via callback rate | 0.4 | "明显会有二次来电" — requires causal inference |
| 25 | `lookup`: fee_stated == KB.fee, documents_listed ⊇ KB.required | 1.0 | None — fully checkable |

---

## Dimension 4: Proactive Value (weight: 1×)

**What it measures:** Whether the agent went beyond the stated request
to identify unmet needs and offer genuinely useful solutions the
customer didn't know to ask for. Marketing is a subclass of this
dimension — the quality axis is the same (recognize unstated need →
recommend genuinely useful solution), the difference is only whether
the recommended solution generates revenue.

| Item | Rubric entry | Why this axis |
|------|-------------|--------------|
| 20 | 能准确快速抓住营销机会并加以引导 | Trigger identification — problem scenario exposes unstated need. "准确" means the recommendation matches the need. |
| 21 | 积极灵活营销 | Guidance quality — "积极灵活" (explain benefits) vs "简单叙述，由用户自行选择" (passively name-drop) |

**Supporting artifacts:**

| Artifact | Role |
|----------|------|
| `营销话术.md` | 18 standard scripts as truth source for evaluating whether the pitch was active (explains benefit points) vs passive (simple narration). |

**Why marketing is not a separate dimension:** An agent recommending a
mobile certificate because the customer's USB key keeps failing (营销触发
T002) is doing exactly what Proactive Value measures — identifying an
unstated need from the problem scenario, offering a solution that
genuinely makes the customer better off. The evaluation axis is
identical. Revenue is a business outcome, not a service quality
dimension. Marketing differs from general proactive service only in
having a defined trigger set and script library, making it *easier* to
evaluate, not different in kind.

**Compilability:**

| Step | Compilable to | Confidence | Residue |
|------|--------------|-----------|---------|
| P31 trigger detection | `lexical`: customer_utterance ∩ trigger_keywords ≠ ∅ | 1.0 | Implicit triggers — scenario implies need but uses no keyword |
| P32 initiative check | `ordered_relation`: agent mentions service_to_promote AFTER trigger | 1.0 | None |
| P33 skill assessment | Not compilable | — | "积极灵活" vs "敷衍了事" — scripted-vs-genuine in a sales context |

---

## Cross-Axis Items

Three items span two axes. They are not split into sub-items — the
evaluator scores them on the axis where the *primary* failure mode
manifests. If both axes independently fail on the same interaction
segment, both are docked — this is not an anti-stacking violation
because two independent failures occurred.

| Item | Primary axis | Secondary axis | Why it crosses |
|------|-------------|---------------|----------------|
| 9 语速适中，配合客户速度，语音平稳 | Procedural | Empathy & Tone | Acoustic half (speed, volume) is a DSP threshold → Procedural. "配合客户速度" requires judging whether the agent adapted to the customer's pace → Empathy. |
| 15 表达内容重点突出，简明扼要 | Problem Resolution | Empathy & Tone | "抓不住重点" degrades resolution efficiency → Resolution. "啰嗦" degrades customer experience → Empathy. |
| 26 沟通氛围融洽，警觉性高 | Empathy & Tone | Problem Resolution | "氛围融洽" (讽刺, 阴阳怪气) is a tone failure → Empathy. "警觉性" (detecting hidden risks, safety issues) is about resolution completeness → Resolution. |

---

## Summary

| Generic skill dimension | Items | Evaluation nature |
|------------------------|-------|-------------------|
| **Procedural Accuracy** (2×) | 1, 2, 3, 4, 5, 27 + 9 (acoustic half) | 6 full + 1 partial. Mostly compilable to compliance-layer triggers (confidence 0.85–1.0). |
| **Empathy & Tone** (3×) | 8, 10, 11, 12, 13, 14, 22, 26 (primary) + 9 (empathy half) | 8 full + 2 partial. Heavily LLM-dependent. The scripted-vs-genuine blind spot (items 11, 22) is the highest-cost false positive. |
| **Problem Resolution** (3×, gate: 7) | 15 (primary), 16, 17, 18, 19, 23, 24, 25 + 26 (警觉性 half) | 7 full + 2 partial. Mixed — items 19, 25 are fully compilable (`lookup`), items 16, 18, 23, 24 require semantic judgment. |
| **Proactive Value** (1×) | 20, 21 + 营销触发.md + 营销话术.md | 2 items + external truth sources. P31/P32 fully compilable (confidence 1.0); P33 remains LLM-dependent. |

**Total: 25 items across 4 dimensions (items 6, 7 excluded).**

---

## Remaining Gaps

Items not covered by either the 27-item rubric or the four generic dimensions:

- **Unknown failure modes.** Patterns of poor service that no existing
  rubric item captures. Discovered through baseline call sampling and
  human annotation. These become new Error Case Library entries and
  potential seed items for future rubric iterations.

- **Ethical omissions.** The agent provides factually correct information
  but systematically withholds unfavorable details (e.g., mentions the
  refund policy but omits a faster path). This is neither procedural
  inaccuracy (facts are correct) nor standard empathy failure (tone may
  be warm). Detection requires adversarial evaluation against the full
  KB, not just cited facts.

- **Cross-item interaction effects.** An agent can pass every individual
  item while the *sequence* is problematic — e.g., greeting perfectly
  then immediately interrupting the customer. Individual items 1
  (greeting) and 12 (no interruption) both pass, but the transition is
  jarring. The evaluator skill's Active Testing Protocol partially
  addresses this through ordered-relation checks; complex interaction
  patterns remain residually human-reviewed.

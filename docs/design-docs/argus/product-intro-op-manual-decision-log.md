# Decision Log: Product Introduction & Operation Manual — INTENTS Path and Compiler Integration

**Date:** 2026-07-16
**Status:** draft
**Scope:** argus/9003 · `#4 Product Introduction` · `#5 Operation Manual` · doc2graph · Context-Engineering

---

## Context

The 9 expertise modules include two that describe the domain knowledge evaluators need as reference context: Product Introduction (#4 — what products and services exist) and Operation Manual (#5 — what the standard operating procedures are). These are NOT scoring rules and NOT lexicons — they are **referent knowledge** that evaluators consult to determine whether an agent's actions were correct.

---

## Correction: marketing material is NOT Product Introduction

营销话术.md (18 marketing scripts) and 营销触发.md (TAQ evaluation model) were initially misclassified. Their correct expertise assignment:

| File | Correct expertise | Rationale |
|:---|:---|:---|
| 营销话术.md | **#3 Phrase & Keyword** (Layer 2 — reference corpus) | Script full text serves as the Jaccard comparison baseline for Item 21; it is a lexicon of "what quality marketing looks like" |
| 营销触发.md | **Companion to #3 Phrase & Keyword** | TAQ model (trigger → action → quality) defines how trigger keywords map to evaluation steps; consumed by Items 20, 21 |

---

## Decision 1: #4 Product Introduction = Reference

### What it is

Product knowledge documents describing what products and services exist, their features, pricing, and applicable scenarios. Examples from the CA hotline domain:

| Product | Content |
|:---|:---|
| 子证书 | Function: identical to parent certificate. Scenario: multiple people need to use certificate, bidding conflicts with annual report. |
| 移动证书 | Function: mobile-phone-based certificate, no USB key needed. Advantage: 手机扫码登录, 操作方便. Contrast: 介质证书会老化, 需要驱动. |
| 印章定制 | Service: 定制与实物章一致的电子章 (公章, 法人章, 签字章). Pricing: varies by type. |
| VIP 服务 | Service tiers: 供应商入驻, 商品上架 (300元起步 / 800元/次), 标书代写, 电子保函. |
| 加急处理 | Service: 非工作时间加急, 100元/次. |

### Analysis

| Standard | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | **medium** — new products launch, pricing changes, features evolve | Reference |
| Sharing scope | Items 19 (业务知识), 20, 21, 25 (业务办理) + audio2tree + human agents | Reference |
| Content nature | "What is evaluated against" — determines whether agent gave correct product information | Reference |

### INTENTS Path

Per Context-Engineering.md §5, Product Introduction lives in the INTENTS tree as doc2graph-processed `index.md`:

```
INTENTS/
  数字证书客服热线/                          ← L1 domain
    产品知识/                                ← L2 intent
      证书类型/                              ← L3 intent
        index.md                            ← 子证书, 移动证书, 介质证书
        /assets/
      增值服务/                              ← L3 intent
        index.md                            ← 印章定制, VIP服务, 加急处理
        /assets/
```

### Producer: doc2graph

```
Product spec docs (raw)  →  doc2graph  →  INTENTS/<L1>/产品知识/<L3>/index.md
```

### Consumer: Evaluator via INTENTS Provider

Item YAML references the INTENTS path. Evaluator loads product knowledge as reference context when scoring Items that require product knowledge verification.

```yaml
# Item 19 (业务知识) YAML
reference_sources:
  product_intro:
    intents_path: "数字证书客服热线/产品知识/"
    pinned_sha: "<git SHA at compile time>"
    role: "verify agent product claims against authoritative product descriptions"
```

---

## Decision 2: #5 Operation Manual = Reference

### What it is

Standard operating procedures describing how business processes should be executed. Examples from the CA hotline domain:

| Procedure | Content |
|:---|:---|
| 证书续期流程 | Steps: verify certificate type → check expiry → confirm fees → guide renewal → confirm success |
| 投诉升级处理规范 | Steps: acknowledge complaint → log details → escalate to supervisor within SLA → follow up with customer |
| 年报/政务网登录操作指南 | Steps for guiding customers through 年报 and 政务网 login using digital certificates |
| 远程协助操作规范 | When to initiate remote session, how to confirm customer consent, post-session steps |

### Analysis

| Standard | Assessment | Direction |
|:---|:---|:--:|
| Update frequency | **medium** — procedures change with policy and system updates | Reference |
| Sharing scope | Items 3 (信息查询), 4 (候线规范), 6★ (服务记录), 7★ (问题升级), 17 (主动引导), 25 (业务办理) + audio2tree + human agents | Reference |
| Content nature | "What is evaluated against" — determines whether agent followed correct procedure | Reference |

### INTENTS Path

```
INTENTS/
  数字证书客服热线/                          ← L1 domain
    操作规范/                                ← L2 intent
      证书续期/                              ← L3 intent
        index.md                            ← 续期标准操作流程
        /assets/
      投诉升级/                              ← L3 intent
        index.md                            ← 投诉升级处理规范
        /assets/
      远程协助/                              ← L3 intent
        index.md                            ← 远程协助操作规范
        /assets/
```

### Producer: doc2graph

```
SOP docs (raw)  →  doc2graph  →  INTENTS/<L1>/操作规范/<L3>/index.md
```

### Consumer: Evaluator via INTENTS Provider

```yaml
# Item 4 (候线规范) YAML
reference_sources:
  operation_manual:
    intents_path: "数字证书客服热线/操作规范/"
    pinned_sha: "<git SHA at compile time>"
    role: "verify agent hold/transfer procedure compliance"
```

---

## Decision 3: Product Introduction and Operation Manual are epistemic peers in the INTENTS tree

Both are **descriptive facts** (ADR-0001), produced by doc2graph from raw documentation, stored under the same L1→L2→L3 hierarchy (Context-Engineering §5), and consumed by evaluators as reference context. Their INTENTS paths differ only by L2 intent category.

| | #4 Product Introduction | #5 Operation Manual |
|:---|:---|:---|
| Epistemic class | Descriptive facts | Descriptive facts |
| L2 intent | `产品知识/` | `操作规范/` |
| L3 intent | Product/service categories | Procedure categories |
| File | `index.md` | `index.md` |
| Producer | doc2graph | doc2graph |
| Update cadence | medium | medium |
| Consumer | Evaluator (reference) | Evaluator (reference) |

---

## Decision 4: Both are REFERENCE — never embedded in Item YAML

Three standards all converge on reference for both expertise types. They are independent of rubric version — product knowledge and procedures change on their own cadence, and Items that reference them should benefit from updates without recompilation.

### Compiler integration

The 9003 compiler does NOT read Product Introduction or Operation Manual content during compilation. These are evaluator runtime dependencies. The compiler only needs to know:

1. That a given Item requires product knowledge or procedural reference (declared in the Item's compilation metadata)
2. The INTENTS paths where the evaluator should find that content at runtime

The evaluator's RubricReader loads the content at the pinned SHA when evaluating calls. Item YAMLs declare their reference dependencies, and the evaluator's pre-flight check verifies all referenced INTENTS paths exist before scoring begins.

---

## Cross-references

- **Context-Engineering.md §5**: Operation Manual folder structure (L1→L2→L3 hierarchy with index.md)
- **ADR-0001**: epistemic classification (descriptive facts)
- **ADR-0002**: INTENTS path-as-ontology, bottom-up authority
- **ADR-0004**: expertise library as runtime artefact; RubricReader
- **phrase-keyword-decision-log.md**: #3 Phrase & Keyword — 16 marketing scripts correctly belong here
- **measurement-profiles-design.md**: shared data infrastructure

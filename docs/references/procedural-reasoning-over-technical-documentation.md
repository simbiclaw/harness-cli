 <alphaxiv-thinking-title title="Searching for procedural reasoning papers" /> 

 

 <alphaxiv-thinking-title title="Compiling paper summaries" />

Here are the key papers focused on **procedural reasoning over technical documentation** (operational knowledge), organized by relevance:

| Paper | Focus | Why It Matters |
|-------|-------|--------------|
| [FreshStack](https://arxiv.org/abs/2504.13128) | **The KARLBench component** — procedural reasoning over fast-growing technical software documentation. Questions cover plugin troubleshooting, data pipeline configuration, etc. | Directly tests the CA-application-style workflow you described; uses community Q&A pairs from Stack Exchange to ensure answer verifiability even when documentation is incomplete |
| [ProcBench](https://arxiv.org/abs/2410.03117) | Multi-step procedural following — instruction pairs where procedures are *explicitly* provided | Isolates the "step-following" aspect from retrieval; diagnostic for whether LLMs can execute explicit procedures |
| [Extracting Procedural Knowledge from Technical Documents](https://arxiv.org/abs/2010.10156) | Extracting procedures from tech docs — foundational work on procedure identification | Encodes the challenge of recognizing procedural text (steps, prerequisites, conditions) in unstructured documentation |
| [Knowing-how & Knowing-that](https://arxiv.org/abs/2306.04187) | MRC over user manuals distinguishing "knowing that X exists" vs "knowing how to do X" | Formalizes the procedural/epistemic distinction in documentation understanding |
| [Procedural Knowledge Extraction from Industrial Troubleshooting Guides](https://arxiv.org/abs/2601.22754) | Extracting diagnostic procedures from flowchart-like industrial troubleshooting diagrams | Most recent work — operational knowledge for industrial/maintenance contexts; uses VLMs to parse graphical + textual procedures |
| [Neuro Symbolic Knowledge Reasoning for Procedural Video](https://arxiv.org/abs/2503.14957) | Procedural reasoning from *videos* (cooking, assembly), not text | Shows procedural reasoning beyond documentation — converging capability |

---

## The Framing Thread Across These Papers

All converge on the same insight: **procedural knowledge in documentation is structured (steps, conditions, dependencies) but expressed in unstructured natural language**. The research challenge is two-fold:

1. **Extract/recognize** that underlying structure from messy docs
2. **Execute/verify** procedures in context — tracking state, detecting prerequisites, handling conditional branches

FreshStack is the closest operational analog to your CA application scenario: questions require navigating fragmented documentation to produce a step-by-step resolution. The [2601.22754] paper extends this to industrial contexts where procedures are often visual (flowcharts), making it even closer to the "IT runbook with diagrams" reality.
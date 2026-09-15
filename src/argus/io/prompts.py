# argus/io/prompts.py
"""Ported from simbi `models/prompts.py` @ 929d5a7, re-namespaced.

Verbatim. `ROLE_DETECTION_PROMPT` is already absent at the source commit
(deleted by 9023 M2 — role re-derivation is the producer's). The duplicate
`REPORT_SUMMARY_PROMPT` definition is kept as shipped: the later assignment
shadows the earlier one, and the orchestrator's summary call is written
against the shadowing "完整版" template — deleting the dead first definition
is a cleanup for B's repo, not this port's business.
"""

# ── Stage 0 ──────────────────────────────────────────────────
ENTITY_EXTRACTION_PROMPT = """
从以下客服对话中提取关键业务实体。

对话：
{transcript}

提取以下类型的实体：
- 平台名称（如：金华市公共资源交易中心、浙里办、政采云）
- 产品名称（如：USB-Key、CA证书、移动证书）
- 错误代码或状态（如：E3、已公示、经营异常）
- 业务关键词（如：年报、延期、解锁、营业执照）
- 企业名称
- 来电号码

输出JSON：
{{
  "platforms": [],
  "products": [],
  "error_codes": [],
  "business_keywords": [],
  "company_name": "",
  "phone_number": ""
}}
"""

# LLM兜底L1分类
LLM_L1_CLASSIFY_PROMPT = """
以下是知识库的一级目录列表：
{l1_dirs}

客户对话实体：{entities}
对话摘要（前300字）：{transcript_summary}

请选择最相关的1-2个目录名（原文选取）。
若都不相关返回空列表。
输出JSON：{{"selected": ["目录名"]}}
"""
#L2分类
L2_CLASSIFICATION_PROMPT = """
以下是知识库"{l1_path}"目录下的子目录：
{children_list}

客户对话关键词：{keywords}
对话关键片段：{snippet}

请选择最相关的1-2个子目录（原文选取，不要修改）。
如果都不相关，返回空列表。

输出JSON：{{"selected": ["子目录名"]}}
"""

# ── Stage 2 ──────────────────────────────────────────────────
ATOMIZE_CLIENT_PROMPT = """
你是专业的对话分析师。分析以下客服对话，
提取【客户侧】所有原子化陈述。

原子化规则（WikiChat标准）：
1. 每个原子必须是单一命题，不可再分
2. 去语境化：消解所有代词和指代（"这个"→具体内容，"他们"→具体机构）
3. 自足性：无需上下文即可独立理解和验证

客户原子类型：
- 事实声明：客户陈述的可验证事实
- 故障描述：客户遇到的具体问题
- 明确诉求：客户明确要求的处理结果
- 历史声称：客户提及的历史承诺或过去交互
- 推断声称：客户基于观察做出的推断
- 异议：客户对客服解释的质疑

对话：
{transcript}

输出JSON数组：
[{{
  "id": "CA-01",
  "source_turn_ids": ["T01"],
  "role": "client",
  "atom_type": "明确诉求",
  "content": "原文摘录",
  "decontextualized": "去语境化的自足陈述"
}}]
"""

ATOMIZE_AGENT_PROMPT = """
你是专业的对话分析师。分析以下客服对话，
提取【客服侧】所有原子化陈述。

原子化规则同上（去语境化、自足性、单一命题）。

客服原子类型：
- 业务判断：客服对业务情况的判断
- 事实陈述：客服陈述的客观事实
- 政策引用：客服引用的公司政策或规定
- 故障定性：客服对产品/系统问题的技术判断
- 解决方案：客服提供的处理建议
- 操作指引：客服提供的具体操作步骤
- 服务承诺：客服作出的承诺
- 结案行为：客服结束对话的方式
- 服务行为：客服的具体服务动作

领域知识背景：
{domain_knowledge_summary}

对话：
{transcript}

输出JSON数组（格式同上，id前缀为AA）
"""

COVERAGE_MATRIX_PROMPT = """
分析以下客户原子和客服原子，判断每个客户原子是否被客服有效响应。

判断标准（需结合业务知识）：
- responded：客服完整响应了该诉求，且响应内容准确充分
- partial：客服有所回应，但不完整、不准确、或转移了焦点
- ignored：客服完全没有回应该诉求

业务知识上下文：
{domain_knowledge_summary}

客户原子：
{client_atoms_json}

客服原子：
{agent_atoms_json}

对话原文：
{transcript}

输出JSON数组：
[{{
  "client_atom_id": "CA-01",
  "agent_atom_id": "AA-03",
  "status": "responded/partial/ignored",
  "note": "说明判断依据"
}}]
"""

# ── Stage 3 ──────────────────────────────────────────────────
INTENT_INFERENCE_PROMPT = """
基于以下对话分析结果，推断双方的真实意图和行为模式。

对话原文：
{transcript}

客户原子：
{client_atoms_json}

客服原子：
{agent_atoms_json}

未被充分响应的客户原子：
{unresponded_atoms_json}

业务知识上下文：
{domain_knowledge_summary}

请分析：
1. customer_surface_intent：客户来电的表层目的
2. customer_deep_intent：客户真正希望得到的结果（超越表面）
3. agent_behavior_pattern：客服的行为模式
   （是否有效解决/是否转移/是否回避/是否主动引导）
4. key_tension：双方意图之间的核心张力点
5. intent_switches：对话中的意图切换节点（客户从A话题转向B话题）
   以及客服是否识别到了这些切换
6. unresolved_intents：挂机时仍未解决的客户诉求列表

输出JSON：
{{
  "customer_surface_intent": "...",
  "customer_deep_intent": "...",
  "agent_behavior_pattern": "...",
  "key_tension": "...",
  "intent_switches": [
    {{"turn_id": "T05", "from_intent": "...",
      "to_intent": "...", "agent_recognized": true/false}}
  ],
  "unresolved_intents": ["..."]
}}
"""

# ── Stage 4 ──────────────────────────────────────────────────
RUBRIC_TO_QUESTION_PROMPT = """
将以下质检规则转化为一个针对本通电话的 Yes-No 子问题。

质检规则：
- 规则ID：{rubric_id}
- 规则名称：{rubric_name}
- 通过标准（1分）：{pass_criteria}
- 不通过标准（0分）：{fail_criteria}
- NA标准：{na_criteria}

相关客服原子：
{relevant_agent_atoms}

相关对话片段：
{relevant_turns}

任务：
1. 判断该规则是否适用于本通电话（参考NA标准）
2. 若适用，生成一个具体的 Yes-No 子问题
3. 生成正向陈述句（用于NLI：若答案为Yes，这句话成立）
4. 生成否定陈述句（用于NLI：若答案为No，这句话成立）

输出JSON：
{{
  "applicability": "applicable/NA",
  "na_reason": "若NA，说明原因",
  "question": "客服是否...？",
  "hypothesis_pos": "客服在本次通话中...（正向陈述）",
  "hypothesis_neg": "客服在本次通话中未...（否定陈述）",
  "relevant_turn_ids": ["T01", "T02"]
}}
"""

GENERATE_ACCURACY_LITERAL_Q_PROMPT = """
基于以下客服的业务陈述和知识库内容，
生成用于核查业务准确性的 Yes-No 子问题。

客服原子（政策引用/故障定性类）：
{agent_atom_json}

知识库相关内容：
{kb_content}

质检规则要求（业务准确性相关）：
{accuracy_rubrics}

生成子问题，核查客服的陈述是否与知识库一致。
同时生成正向和否定陈述句。

输出JSON：
{{
  "question": "...",
  "hypothesis_pos": "...",
  "hypothesis_neg": "...",
  "claim_type": "internal_policy/external_fact",
  "key_kb_reference": "最关键的知识库原文片段"
}}
"""

GENERATE_IMPLIED_Q_PROMPT = """
基于以下信息，生成【Implied 质检子问题】。

Implied 子问题：评估客服是否识别并响应了客户的隐性诉求，
不能直接从对话文本验证，需要推断。

未被充分响应的客户原子：
{unresponded_atoms_json}

意图推断结果：
{intent_inference_json}

业务知识上下文：
{domain_knowledge_summary}

质检规范要求：
{qa_rubrics_summary}

Implied Q 类型（选择最合适的一种）：
- DOMAIN_KNOWLEDGE：需要专业领域知识才能判断
- CONTEXT：需要了解背景情境才能判断
- IMPLICIT_MEANING：需要解读说话者言外之意
- STATISTICAL_RIGOR：需要检验表述的统计/逻辑严谨性

输出JSON数组（每个未响应原子生成1个Implied Q）：
[{{
  "question": "...",
  "implied_q_type": "DOMAIN_KNOWLEDGE/CONTEXT/IMPLICIT_MEANING/STATISTICAL_RIGOR",
  "hypothesis_pos": "...",
  "hypothesis_neg": "...",
  "source_atom_id": "CA-XX",
  "reasoning": "为什么这是一个重要的隐性问题"
}}]
"""

# ── Stage 5 路径B ─────────────────────────────────────────────
WIKICHAT_VERIFY_PROMPT = """
你是一个事实核查员。仅根据以下提供的知识库内容判断陈述是否正确。
不要使用你自己的知识，只基于提供的文档。

待核查陈述：
{hypothesis}

知识库内容：
{retrieved_content}

判断标准：
- Supported：知识库明确支持该陈述
- Refuted：知识库明确反驳该陈述
- NEI：知识库中没有足够信息判断（Not Enough Information）

输出JSON：

{{
  "verdict": "Supported/Refuted/NEI",
  "confidence": 0.0-1.0,
  "reasoning": "判断依据",
  "key_evidence": "最关键的证据原文片段"
}}
"""

REPORT_SUMMARY_PROMPT = """
基于以下质检结果，生成简洁的质检总结（3-5句话）
和3条具体的改进建议。

总分：{overall_score}/100
各维度得分：{dimension_scores_json}
主要不通过项：{failed_items_json}
触发人工复核：{human_review_count}项
未解决客户诉求：{unresolved_intents}

输出JSON：
{{
  "summary": "...",
  "improvement_suggestions": ["建议1", "建议2", "建议3"]
}}
"""

# Stage 6 —— 报告总结（完整版）
REPORT_SUMMARY_PROMPT = """
基于以下质检结果，生成简洁的质检总结（3-5句话）
和3条具体的改进建议。

综合得分：{overall_score}/100
评级：{grade}
各维度得分：{dimension_scores_json}
主要不通过项：{failed_items_json}
需人工复核项数：{human_review_count}
客户未解决诉求：{unresolved_intents}
一票否决触发：{veto_triggered}

要求：
- 总结客观描述本次通话的整体表现
- 点明最关键的1-2个问题
- 3条建议必须具体可操作，不能是泛泛而谈
- 若有未解决诉求，建议中必须包含相关改进

输出JSON：
{{
  "summary": "...",
  "improvement_suggestions": [
    "建议1（具体）",
    "建议2（具体）",
    "建议3（具体）"
  ]
}}
"""

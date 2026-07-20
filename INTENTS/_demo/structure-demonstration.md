# INTENTS 目录结构完整演示

**基于决策日志 (expertise-decision-log.md) 的 8 类 Expertise 存储方案**

---

## Grounding Files (源文件)

本演示文件基于以下权威文档生成，用于 review 时交叉验证：

| 文档 | 路径 | 作用 |
|:-----|:-----|:-----|
| **Expertise Decision Log** | `docs/design-docs/argus/expertise-decision-log.md` | **主要决策依据** — 8 类 Expertise 的 Embed vs Reference 决策 (#1-#8) |
| **Soft Criteria Patch 1** | `docs/retrospectives/soft-criteria-authoring-spec-v4-patch-1.md` | 25 Items 维度划分 (4 dimensions)、`_rubric/` 三层结构定义 |
| **Context Engineering** | `docs/PRD/Context-Engineering.md` | **L1/L2/L3 中文意图层级**的真实示例来源 |
| **ADR-0001** | `docs/adr/0001-*.md` | 三种认识论分类 (Versioned Rubric / Descriptive Facts / Accumulated History) |
| **ADR-0002** | `docs/adr/0002-intents-path-as-ontology.md` | 路径即本体论、bottom-up authority |
| **ADR-0004** | `docs/adr/0004-expertise-library-*.md` | 9→3 category readers 架构 |

### 关键决策摘要 (来自 Grounding Files)

| # | Expertise | 策略 | 决策依据 |
|:--|:---|:--:|:---|
| 1 | Rules & Criteria | N/A (output) | Patch 1 §3: `_rubric/rules_criteria/` 是编译器输出 |
| 2 | Acoustic Feature | **REFERENCE** | Decision Log #2: 9 Items + audio2tree 共享 |
| 3 | Phrase & Keyword | **L1 REF + L2 EMBED** | Decision Log #3: Layer 1 共享词库 + Layer 2 Item 内联 |
| 4 | Product Introduction | **REFERENCE** | Decision Log #4: L1 单文件 `product-intro.md` |
| 5 | Operation Manual | **REFERENCE** | Decision Log #5 + Context-Engineering.md §5: L1/L2/L3 + `index.md` |
| 6 | Dynamic Knowledge Base | **REFERENCE** | Decision Log #6: L1+L2, `dkb.<slug>.yaml`, parent/extends/overrides |
| 7 | Best Practice Cookbook | **REFERENCE** | Decision Log #7: L1+L2, `cookbook.<slug>.yaml` |
| 8 | Error Case Library | **REFERENCE** | Decision Log #8: L1+L2, `errors.<slug>.yaml` |

### 与 Context-Engineering.md 的对齐

本演示采用该文档中的真实中文意图示例：
- **L1**: `法人数字证书业务` (原示例)
- **L2**: `证书维护` (含 证书申领/证书维护/专项证书业务/移动证书使用)
- **L3**: `证书延期` (含 证书信息变更/证书延期/证书补办/证书解锁)

---

**示例音频文件：**
- `WG1300!DNIS57188234636!1784197487.wav` → CallRecord: `WG1300!DNIS57188234636!1784197487.json`
- `WG6900!DNIS57188234636!1784197087.wav` → CallRecord: `WG6900!DNIS57188234636!1784197087.json`

**假设业务场景（基于 Context-Engineering.md 真实示例）：**
- **L1 Domain:** `法人数字证书业务`
- **L2 Case:** `证书维护`
- **L3 Intent:** `证书延期`

---

## 25 Items 维度划分 (4 Dimensions)

基于 Patch 1 的 Item→Dimension 映射：

| Dimension | Items | Count | 中文名 |
|:----------|:------|:-----:|:-------|
| **procedural_accuracy** | 01-07 | 7 | 程序规范 — 起接语、称谓、候线、结束语等 |
| **empathy_and_tone** | 08-09, 11-13, 17-18, 26 | 8 | 共情与语气 — 语速、耐心、情绪同步、安抚 |
| **problem_resolution** | 10, 14-16, 19, 22-24 | 8 | 问题解决 — 理解、方案、知识、升级处理 |
| **proactive_value** | 20-21 | 2 | 主动价值 — 营销触发识别、营销用语规范 |

**Evidence 依赖分布：**
- Empathy & Tone: 75% 需要 Acoustic + Phrase
- Proactive Value: 100% 需要 Phrase，0% Acoustic
- Problem Resolution: 12% 需要 Acoustic/Phrase (主要依赖 KB)

---

## 完整目录树

```
INTENTS/
│
├── AGENTS.md                         # Agent 路由索引 (导航协议)
├── EPOCH.yaml                        # EPOCH 定义：当前 INTENTS 版本 (ADR-0002)
│
├── _meta/
│   ├── ownership.yaml                # producer → file glob 映射
│   └── residue-manifest.yaml         # 编译器残留清单 (9003)
│
├── _rubric/                          # 【Expertise #1】Rules & Criteria (Compiler 输出)
│   │
│   ├── rules_criteria/               # 25 Items 编译输出 (4 dimensions)
│   │   ├── procedural_accuracy/      # 7 items — 程序规范
│   │   │   ├── item-01.yaml          # 起接语规范
│   │   │   ├── item-02.yaml          # 称谓语规范
│   │   │   ├── item-03.yaml          # 沟通确认
│   │   │   ├── item-04.yaml          # 候线规范
│   │   │   ├── item-05.yaml          # 结束语规范
│   │   │   ├── item-06.yaml          # 操作规范
│   │   │   └── item-07.yaml          # 系统操作
│   │   ├── empathy_and_tone/         # 8 items — 共情与语气
│   │   │   ├── item-08.yaml          # 口语限制
│   │   │   ├── item-09.yaml          # 语速控制
│   │   │   ├── item-11.yaml          # 耐心表现
│   │   │   ├── item-12.yaml          # 语气友善
│   │   │   ├── item-13.yaml          # 积极回应
│   │   │   ├── item-17.yaml          # 情绪同步
│   │   │   ├── item-18.yaml          # 声音品质
│   │   │   └── item-26.yaml          # 安抚技巧
│   │   ├── problem_resolution/       # 8 items — 问题解决
│   │   │   ├── item-10.yaml          # 理解确认
│   │   │   ├── item-14.yaml          # 方案提供
│   │   │   ├── item-15.yaml          # 解释清晰
│   │   │   ├── item-16.yaml          # 跟进承诺
│   │   │   ├── item-19.yaml          # 业务知识
│   │   │   ├── item-22.yaml          # 情绪识别
│   │   │   ├── item-23.yaml          # 升级处理
│   │   │   └── item-24.yaml          # 闭环确认
│   │   └── proactive_value/          # 2 items — 主动价值
│   │       ├── item-20.yaml          # 营销触发识别
│   │       └── item-21.yaml          # 营销用语规范
│   │
│   ├── evidence/                     # 【Expertise #2, #3】测量框架 + 词库
│   │   │
│   │   ├── acoustic/                 # 【#2】Acoustic Feature (REFERENCE)
│   │   │   ├── indicators.yaml       # 12 声学指标定义
│   │   │   ├── emotion-profiles.yaml # anger, anxiety, confusion fingerprints
│   │   │   └── attitude-profiles.yaml
│   │   │
│   │   └── phrase-keyword/           # 【#3】Phrase & Keyword (Layer 1: REFERENCE)
│   │       ├── customer-emotion/     # ~90 terms
│   │       │   ├── escalation-threat.yaml
│   │       │   ├── deception-perception.yaml
│   │       │   ├── price-dissatisfaction.yaml
│   │       │   └── ...
│   │       ├── agent-attitude/       # ~60 terms
│   │       │   ├── politeness.yaml
│   │       │   ├── dismissive.yaml
│   │       │   └── confrontational.yaml
│   │       ├── agent-competence/     # ~22 terms
│   │       ├── interaction-patterns/ # ~18 patterns
│   │       │
│   │       └── marketing-scripts.yaml # 【#3 Layer 2 corpus】16 个营销话术脚本
│   │
│   └── gates/                        # 评分门控配置
│       ├── coverage-gates.yaml
│       └── agreement-gates.yaml
│
├── 法人数字证书业务/               # 【L1 Domain】法人数字证书业务
│   │
│   ├── product-intro.md              # 【Expertise #4】Product Introduction (REFERENCE)
│   │                                   # 单文件，L1 级别，Markdown 格式
│   │
│   ├── dkb.service-hours.yaml        # 【Expertise #6】DKB L1 (Domain-global)
│   ├── dkb.pricing-base.yaml         # 【#6】DKB L1：基础定价
│   ├── cookbook.service-recovery.yaml # 【Expertise #7】Cookbook L1
│   └── errors.common-misses.yaml     # 【Expertise #8】Errors L1
│   │
│   ├── 证书申领/                     # 【L2 Case】证书申领
│   │   ├── 子证书申领/               # 【L3 Intent】子证书申领
│   │   │   ├── index.md              # 【#5】Operation Manual L3
│   │   │   └── assets/
│   │   └── 母证书申领/               # 【L3 Intent】母证书申领
│   │       ├── index.md
│   │       └── assets/
│   │
│   ├── 证书维护/                     # 【L2 Case】证书维护 (示例场景)
│   │   │
│   │   ├── dkb.certificate-maintenance.yaml # 【#6】DKB L2 (Case-specific)
│   │   ├── cookbook.maintenance-guide.yaml  # 【#7】Cookbook L2
│   │   └── errors.maintenance-escapes.yaml  # 【#8】Errors L2
│   │   │
│   │   ├── 证书信息变更/             # 【L3 Intent】证书信息变更
│   │   │   ├── index.md              # 【#5】Operation Manual
│   │   │   └── assets/
│   │   │
│   │   ├── 证书延期/                 # 【L3 Intent】证书延期 (示例场景)
│   │   │   ├── index.md              # 【#5】Operation Manual L3
│   │   │   ├── assets/               # 操作手册截图
│   │   │   │   ├── img_1.png
│   │   │   │   └── img_2.png
│   │   │   │
│   │   │   └── calls/                # Audio Transcription 存储 (非 Expertise)
│   │   │       └── 2026-07-16/
│   │   │           ├── WG1300!DNIS57188234636!1784197487.json
│   │   │           └── WG6900!DNIS57188234636!1784197087.json
│   │   │
│   │   ├── 证书补办/                 # 【L3 Intent】证书补办
│   │   │   ├── index.md
│   │   │   └── assets/
│   │   │
│   │   └── 证书解锁/                 # 【L3 Intent】证书解锁
│   │       ├── index.md
│   │       └── assets/
│   │
│   ├── 专项证书业务/                 # 【L2 Case】专项证书业务
│   │   ├── 义务电子合同数智服务平台操作手册/       # 【L3 Intent】
│   │   ├── 杭州城建档案馆数字证书申领及聚安PDF电子签章操作手册/  # 【L3】
│   │   └── 浙江省公共交易平台汇信证书申领及维护指南/  # 【L3】
│   │
│   └── 移动证书使用/                 # 【L2 Case】移动证书使用
│       ├── index.md
│       └── assets/
│
├── 年报业务/                         # 【L1 Domain】年报业务
│   ├── product-intro.md
│   ├── 企业多报合一/
│   ├── 个体工商户年报/
│   └── ...
│
├── 信用修复业务/                     # 【L1 Domain】信用修复业务
│   ├── 严重违法失信名单移出/         # 【L2】
│   ├── 经营异常名录移出/             # 【L2】
│   └── 行政处罚信息修复/             # 【L2】
│
├── 公司设立变更注销业务/             # 【L1 Domain】公司设立变更注销业务
│   ├── 公司变更/                     # 【L2】
│   │   ├── 企业减资公告/             # 【L3】
│   │   ├── 企业分立公告/             # 【L3】
│   │   ├── 企业即时信息/             # 【L3】
│   │   └── 企业合并公告/             # 【L3】
│   ├── 公司注销/                     # 【L2】
│   │   ├── 注销公告/                 # 【L3】
│   │   └── 注销登记/                 # 【L3】
│   └── 公司设立/                     # 【L2】
│
└── 电子印章和签章业务/               # 【L1 Domain】电子印章和签章业务
    ├── PDF电子签章/                  # 【L2】
    ├── 个人印章/                     # 【L2】
    ├── 单位印章管理/                 # 【L2】
    └── 电子签名/                     # 【L2】
```

---

## 关键文件内容示例

### 1. EPOCH.yaml (INTENTS 版本锚定)

```yaml
# EPOCH.yaml
epoch_id: "2026-07-16-alpha"
created_at: "2026-07-16T14:30:00Z"
git_sha: "a1b2c3d4e5f6789012345678901234567890abcd"
parent_epoch: "2026-07-15-beta"

domains:
  - name: "法人数字证书业务"
    path: "法人数字证书业务"
    cases:
      - name: "证书申领"
        path: "法人数字证书业务/证书申领"
        l3_intents:
          - "子证书申领"
          - "母证书申领"
      - name: "证书维护"
        path: "法人数字证书业务/证书维护"
        l3_intents:
          - "证书信息变更"
          - "证书延期"
          - "证书补办"
          - "证书解锁"
      - name: "专项证书业务"
        path: "法人数字证书业务/专项证书业务"
      - name: "移动证书使用"
        path: "法人数字证书业务/移动证书使用"
```

---

### 2. Item YAML 引用示例 (Item-20: 营销触发识别)

```yaml
# _rubric/rules_criteria/sales-marketing/item-20.yaml
item_id: 20
item_name: "营销触发识别与响应"
dimension: "proactive_value"

# 【#3 Layer 2 EMBED】Item-specific vocabulary (inline)
vocabulary:
  trigger_mapping:
    T001: { keywords: ["费用", "多少钱", "价格"], service: "pricing_inquiry" }
    T002: { keywords: ["怎么办理", "如何申请"], service: "application_guide" }
    # ... T003-T011

# 【#2 REFERENCE】Acoustic Feature
reference_sources:
  acoustic_framework:
    path: "_rubric/evidence/acoustic/indicators.yaml"
    pinned_sha: "a1b2c3d4"
  emotion_profile:
    path: "_rubric/evidence/acoustic/emotion-profiles.yaml"
    section: "interest_excitement"

# 【#3 Layer 1 REFERENCE】Shared lexicons
corroborators:
  - type: "lexicon"
    path: "_rubric/evidence/phrase-keyword/customer-emotion/escalation-threat.yaml"
    pinned_sha: "a1b2c3d4"
  - type: "lexicon"
    path: "_rubric/evidence/phrase-keyword/agent-attitude/dismissive.yaml"
    pinned_sha: "a1b2c3d4"\n
# 【#3 Layer 2 corpus REFERENCE】Marketing scripts
marketing_scripts_ref:
  path: "_rubric/evidence/phrase-keyword/marketing-scripts.yaml"
  pinned_sha: "a1b2c3d4"
  scripts: ["S2", "S3", "S4", "S5", "S6", "S9", "S10", "S11", "S12", "S15", "S16", "S17", "S18"]

# 【#4 REFERENCE】Product Introduction
product_intro_ref:
  path: "法人数字证书业务/product-intro.md"
  pinned_sha: "a1b2c3d4"

# 【#5 REFERENCE】Operation Manual (L3 specific)
operation_manual_ref:
  path: "法人数字证书业务/证书维护/证书延期/index.md"
  pinned_sha: "a1b2c3d4"

# 【#6 REFERENCE】Dynamic Knowledge Base (L2 case-specific)
dkb_refs:
  - dkb_id: "certificate-maintenance"
    level: "L2"
    case: "证书维护"
    path: "法人数字证书业务/证书维护/dkb.certificate-maintenance.yaml"
    pinned_sha: "a1b2c3d4"

# 【#7 REFERENCE】Best Practice Cookbook
cookbook_refs:
  - cookbook_id: "maintenance-guide"
    level: "L2"
    case: "证书维护"
    path: "法人数字证书业务/证书维护/cookbook.maintenance-guide.yaml"
    pinned_sha: "a1b2c3d4"
    apply_to_signals: ["F2_service_explained", "F3_steps_clear"]

# 【#8 REFERENCE】Error Case Library
errors_refs:
  - errors_id: "maintenance-escapes"
    level: "L2"
    case: "证书维护"
    path: "法人数字证书业务/证书维护/errors.maintenance-escapes.yaml"
    pinned_sha: "a1b2c3d4"
    apply_to_signals: ["F1_procedure_skipped"]
    escape_tier: "coverage_gap"

# Item 评分标准 (embed)
machine_criterion:
  gap_type: "missed_opportunity"
  applicability_gate:
    condition: "电话中存在合适的营销触发点"
  
signals:
  fail:
    - id: "F1"
      name: "trigger_missed"
      description: "客户表达了营销触发点，坐席未识别或响应"
  excellence:
    - id: "E1"
      name: "trigger_proactively_addressed"
      description: "坐席主动识别触发点并提供完整解决方案"
```

---

### 3. DKB L2 示例 (dkb.certificate-maintenance.yaml)

```yaml
# 法人数字证书业务/证书维护/dkb.certificate-maintenance.yaml
# Type: dkb (dynamic knowledge base)

dkb_id: "certificate-maintenance"
level: "L2"
domain: "法人数字证书业务"
case: "证书维护"
anchor_level: "case"
last_updated: "2026-07-16"
source: "Product team official announcement"

# L1-L2 关联
parent: "dkb.pricing-base"           # 继承 L1 基础定价
extends:                               # 添加 L2 特有内容
  - section: "maintenance_procedures"
overrides:                             # 覆盖 L1 内容
  - section: "service_hours"

content:
  zh_CN: |
    ## 证书维护指南 (2026年8月1日起生效)

    ### 证书延期
    - **标准费用**: 200元/年
    - **VIP客户**: 160元/年 (8折优惠)
    - **延期时限**: 到期前30天内可办理

    ### 证书补办
    - **工本费**: 50元
    - **审核周期**: 1-3个工作日

    ### 证书解锁
    - 需提供: 营业执照副本、法人身份证、解锁申请表
    - 服务热线: 400-xxx-xxxx
```

---

### 4. Cookbook L2 示例 (cookbook.maintenance-guide.yaml)

```yaml
# 法人数字证书业务/证书维护/cookbook.maintenance-guide.yaml
# Type: cookbook (accumulated history)

cookbook_id: "maintenance-guide"
level: "L2"
domain: "法人数字证书业务"
case: "证书维护"
anchor_level: "case"
last_updated: "2026-07-10"
source: "Human reviewer annotation #QA-2026-042"

parent: "cookbook.base-customer-service"
extends:
  - section: "maintenance_patterns"

content:
  zh_CN: |
    ## 证书维护服务最佳实践

    ### 证书延期沟通

    **场景: 客户咨询延期费用**
    - ✅ 优秀做法: "您的证书将于XX天后到期。延期费用200元/年，
      VIP客户享受8折优惠仅需160元。延期即时生效，无需重新审核。"
    - ✅ 主动提醒: "建议您提前办理，避免证书过期影响业务。"

    ### 证书补办引导

    **场景: 客户证书丢失**
    - ✅ 优秀做法: "请先确认证书确实丢失无法找回。补办需要:
      1. 营业执照副本扫描件
      2. 法人身份证正反面
      3. 填写解锁申请表
      工本费50元，1-3个工作日完成。"
    - ⚠️ 避免: 未核实就立即收取费用

    ### 参考案例
    坐席小张处理客户王先生的证书延期，主动告知VIP优惠并协助计算节省费用，
    客户当场完成延期，满意度评分 5/5。

    ### 参考案例
    坐席小王处理客户李女士的价格异议，通过成本对比和剩余时间分析，
    成功说服客户在当天完成续期，客户满意度评分 5/5。
```

---

### 5. Errors L2 示例 (errors.maintenance-escapes.yaml)

```yaml
# 法人数字证书业务/证书维护/errors.maintenance-escapes.yaml
# Type: errors (accumulated history)

errors_id: "maintenance-escapes"
level: "L2"
domain: "法人数字证书业务"
case: "证书维护"
anchor_level: "case"
last_updated: "2026-07-14"
source: "Human reviewer annotation #QA-2026-038"

parent: "errors.common-misses"
extends:
  - section: "maintenance_specific"

content:
  zh_CN: |
    ## 证书维护场景逃逸案例库

    ### 案例 ESC-2026-0714-01: 延期时限未提醒

    **通话日期**: 2026-07-14
    **音频文件**: WG1300!DNIS57188234636!1784197487.wav
    **L3 Intent**: 证书延期

    #### 问题描述
    客户表示"我再考虑几天"，坐席仅回答"好的"，未告知:
    1. 当前剩余天数 (仅剩3天即将过期)
    2. 过期后无法使用证书办理业务
    3. 过期后需补办而非延期，费用更高(250元)

    #### 后果
    - 客户证书过期后业务中断，产生投诉
    - 坐席被认定"未尽告知义务"
    - 客户补办时质疑为何未提前提醒

    #### 检测缺口 (Coverage Gap)
    - Item 19 (业务知识): 未覆盖"延期时限提醒"检查
    - Item 17 (情绪同步): 未识别客户犹豫情绪

    #### 建议修复
    1. 在 Item 19 新增信号: "F4_expiration_deadline_communicated"
    2. 在 DKB 中强化 "延期时限" 条目权重
    3. 在 Cookbook 中补充 "客户犹豫时的紧迫性沟通" 示例

    ---

    ### 案例 ESC-2026-0710-02: 补办材料未一次性告知

    **问题**: 客户咨询证书补办，坐席仅告知需要身份证，未提及营业执照
    **影响**: 客户准备材料不全，多次往返，满意度降至2/5
    **缺口**: Item 6 (操作规范): 未覆盖"材料清单完整性"检查
```

---

### 6. Product Intro 示例

```markdown
<!-- 法人数字证书业务/product-intro.md -->
# Product Introduction — 法人数字证书产品知识
# Type: product-intro (descriptive facts)

## 移动证书 (APP证书)

### 功能与场景
移动数字证书用于：
- 移动端身份认证
- 电子签名 (PDF/表单)
- 扫码登录政务系统

### 产品版本
| 版本 | 年费 | 主要功能 |
|-----|------|---------|
| 标准版 | ¥200 | 基础签名认证 |
| VIP版 | ¥500 | 优先技术支持 + 专属客服 |

### 适用平台
- iOS (12.0+)
- Android (8.0+)

## 介质证书 (USBKey)

### 功能与场景
- PC端身份认证
- 批量签章
- 企业多账号管理

### 证书维护服务
| 服务类型 | 费用 | 办理时限 |
|---------|------|---------|
| 证书延期 | ¥200/年 | 即时生效 |
| 证书补办 | ¥50 | 1-3工作日 |
| 证书解锁 | 免费 | 即时处理 |
| 信息变更 | 免费 | 1工作日 |

---
*最后更新: 2026-07-15*
```

---

### 7. Operation Manual L3 示例

```markdown
<!-- 法人数字证书业务/证书维护/证书延期/index.md -->
# Operation Manual — 证书延期办理规范
# Type: operation-manual (descriptive facts)
# L3 Intent: 证书延期

## 适用范围
客户数字证书即将到期(30天内)或已过期(30天内)，申请延期服务。

## 操作流程

### 步骤1: 核实客户身份与证书信息
| 核实项目 | 操作要求 | 系统操作 |
|---------|---------|---------|
| 企业名称 | 与客户确认营业执照全称 | 在证书管理系统中查询 |
| 证书类型 | 确认是移动证书还是介质证书 | 查看证书详情 |
| 到期时间 | 告知客户当前证书状态 | 显示剩余天数 |
| VIP身份 | 查询客户是否享受优惠 | 查看客户等级 |

### 步骤2: 告知费用与优惠
**标准话术:**
"您的证书还有XX天到期。延期费用为200元/年。"

**VIP客户补充:**
"检测到您是VIP客户，享受8折优惠，实际费用160元/年。"

**已过期客户:**
"您的证书已过期XX天。延期费用200元/年，过期期间业务已暂停，延期后立即恢复。"

### 步骤3: 确认办理意向
- 客户同意办理 → 跳转支付流程
- 客户需考虑 → 提醒时限风险，记录跟进时间
- 客户拒绝 → 询问原因，记录反馈

### 步骤4: 办理与确认
1. 引导客户完成支付
2. 系统操作延期
3. 告知客户新的到期日期
4. 提醒设置到期提醒

## 禁止事项
- ❌ 未核实身份直接告知证书信息
- ❌ 未主动告知VIP优惠
- ❌ 未提醒到期时限风险
- ❌ 承诺"永不收费"等不实信息

## 升级触发条件
- 客户质疑历史费用 → 转费用核查专员
- 客户要求退费 → 转售后主管
- 系统无法延期 → 转技术支撑
```

---

### 8. CallRecord 示例 (Audio Transcription)

```json
{
  "call_id": "WG1300!DNIS57188234636!1784197487",
  "audio_file": "WG1300!DNIS57188234636!1784197487.wav",
  "domain": "法人数字证书业务",
  "case": "证书维护",
  "l3_intent": "证书延期",
  "case": "certificate-renewal",
  "l3_intent": "late-filing-evidence",
  
  "metadata": {
    "dnis": "57188234636",
    "agent_id": "WG1300",
    "call_timestamp": 1784197487,
    "duration_seconds": 342,
    "recording_date": "2026-07-16"
  },
  
  "transcription": {
    "speakers": ["agent", "customer"],
    "turns": [
      {
        "turn_id": 1,
        "speaker": "agent",
        "text": "您好，数字证书客服，工号1300，请问有什么可以帮您？",
        "start_time": 0.5,
        "end_time": 4.2
      },
      {
        "turn_id": 2,
        "speaker": "customer",
        "text": "我的证书过期了，昨天想登录系统续期，结果一直提示系统错误。",
        "start_time": 4.8,
        "end_time": 10.5
      }
      // ... more turns
    ]
  },
  
  "acoustic_measurements": {
    "f0_mean": 220,
    "f0_range": 180,
    "speaking_rate": 4.5,
    "emotion_timeline": [
      {"time": 10.5, "emotion": "confusion", "confidence": 0.7},
      {"time": 45.2, "emotion": "frustration", "confidence": 0.6}
    ]
  },
  
  "lexical_hits": [
    {"term": "系统错误", "lexicon": "deception-perception", "turn_id": 2},
    {"term": "过期", "lexicon": "escalation-threat", "turn_id": 2}
  ]
}
```

---

## Expertise 分布总结

| # | Expertise | 策略 | 位置 | 消费者 |
|:--|:---|:--:|:---|:---|
| 1 | Rules & Criteria | Output | `_rubric/rules_criteria/` | Argus (Evaluator) |
| 2 | Acoustic Feature | REFERENCE | `_rubric/evidence/acoustic/` | Argus + audio2tree |
| 3 | Phrase & Keyword (L1) | REFERENCE | `_rubric/evidence/phrase-keyword/` | Argus + audio2tree |
| 3 | Phrase & Keyword (L2 embed) | EMBED | Item YAML inline | Argus (per Item) |
| 3 | Phrase & Keyword (L2 corpus) | REFERENCE | `_rubric/evidence/phrase-keyword/marketing-scripts.yaml` | Argus (Item 20, 21) |
| 4 | Product Introduction | REFERENCE | `<L1>/product-intro.md` | Argus + Human agents |
| 5 | Operation Manual | REFERENCE | `<L1>/<L2>/<L3>/index.md` (e.g. `法人数字证书业务/证书维护/证书延期/index.md`) | Argus + Human agents |
| 6 | Dynamic Knowledge Base | REFERENCE | `<L1>/dkb.*.yaml` / `<L1>/<case>/dkb.*.yaml` | Argus (运行时) |
| 7 | Best Practice Cookbook | REFERENCE | `<L1>/cookbook.*.yaml` / `<L1>/<case>/cookbook.*.yaml` | Argus (编译时+运行时) |
| 8 | Error Case Library | REFERENCE | `<L1>/errors.*.yaml` / `<L1>/<case>/errors.*.yaml` | Argus (编译时+运行时) |
| — | Audio Transcription | Data | `<L1>/<case>/<L3>/calls/<basename>.json` | Argus (输入) |

---

## 关键设计决策回顾

1. **#4 Product Introduction**: L1 单文件 (`product-intro.md`)，无 L2/L3 层级，因为产品知识通常是 domain-global。示例: `法人数字证书业务/product-intro.md`

2. **#5 Operation Manual**: L1/L2/L3 三级层级，`index.md` 作为 L3 入口。示例: `法人数字证书业务/证书维护/证书延期/index.md`

3. **#6/#7/#8 (DKB/Cookbook/Errors)**: 统一采用 L1+L2 两级 + `parent/extends/overrides` 关联机制。示例: `法人数字证书业务/证书维护/dkb.certificate-maintenance.yaml`

4. **Audio Transcription**: 存储在 INTENTS 但 NOT expertise，按 L3 Intent 分组，basename 匹配输入音频。示例: `法人数字证书业务/证书维护/证书延期/calls/WG1300!...json`

5. **所有 REFERENCE**: 通过 `pinned_sha` 在 Item YAML 中锚定，保证可重现性

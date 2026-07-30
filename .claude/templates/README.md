# Plan Execution Report 模板使用指南

## 模板位置
`.claude/templates/plan-execution-report.html`

## 模板特点

### 1. 仪表板布局（Dashboard-First）
- **顶部 5 个指标卡**：计划健康度、里程碑完成率、Tier C 决策数、验证通过率、Token 消耗
- **颜色编码**：绿色（成功）、黄色（警告）、红色（危险）、蓝色（信息）
- **一目了然的视觉层级**
- **Token 成本表**：按来源分列的消耗明细（实测 + 估算），位于 Surprises 之前

### 2. 响应式两栏布局
- **左侧**：里程碑时间线（带完成状态标记）
- **右侧**：关键决策（Tier C 高亮显示）
- **底部通栏**：Surprises、技术债务、经验教训

### 3. 决策者友好
- 关键信息无需滚动即可看到
- 警告和待办事项 prominently 显示
- 所有链接可直接跳转

---

## 使用方式

### 方式 1：直接调用 Playground（推荐）

在计划完成时，使用以下提示：

```
计划 {{plan_id}} 已完成，生成执行报告 HTML。

模板文件：`.claude/templates/plan-execution-report.html`
输出路径：`docs/exec-plans/reports/{{plan_id}}-report.html`

数据提取要求：
1. 从 `docs/exec-plans/active/{{plan_id}}.md` 提取：
   - Progress 区域的里程碑及状态
   - Decision Log 中的所有决策（标记 Tier C）
   - Surprises & Discoveries
   - Outcomes & Retrospective

2. 从 `.claude/verification/{{plan_id}}/` 提取验证结果

3. 从 `.claude/implementation-notes/{{plan_id}}.md` 提取技术债务

使用 playground skill 渲染 HTML，确保：
- 健康度低于 80% 显示为警告（黄色）
- 有待办决策时显示警告框
- 所有日期格式统一为 YYYY-MM-DD
```

### 方式 2：包装 Skill（自动化）

创建 `.claude/skills/plan-report-generator/`：

```markdown
---
name: plan-report-generator
description: Generate execution report using template
triggers: ["plan completed"]
---

读取 `.claude/templates/plan-execution-report.html` 作为模板，
提取 Plan 数据，调用 playground skill 渲染，
保存到 `docs/exec-plans/reports/{plan-id}-report.html`
```

---

## 模板变量说明

| 变量 | 说明 | 示例 |
|:-----|:-----|:-----|
| `{{plan_id}}` | 计划编号 | `9005` |
| `{{plan_name}}` | 计划名称 | `PEV Loop Evolution` |
| `{{status}}` | 状态 | `completed` / `archived` |
| `{{duration_days}}` | 耗时（天） | `2` |
| `{{duration_hours}}` | 耗时（小时） | `22` |
| `{{completion_date}}` | 完成日期 | `2026-07-30` |
| `{{health_score}}` | 健康度评分 | `85` |
| `{{completed_milestones}}` | 已完成里程碑数 | `10` |
| `{{tier_c_count}}` | Tier C 决策数 | `3` |
| `{{token_total}}` | Token 总计 | `~650K` |
| `{{token_measured}}` | 实测 Token 数 | `81,910` |
| `{{token_estimated}}` | 估算 Token 数 | `~568,000` |
| `{{token_breakdown}}` | Token 分解简述 | `子代理 80K + 剩余估算` |
| `{{commit_count}}` | 提交次数 | `22` |
| `{{files_changed}}` | 变更文件数 | `38` |
| `{{insertions}}` | 新增行数 | `4,137` |
| `{{deletions}}` | 删除行数 | `562` |
| `{{milestones}}` | 里程碑列表（数组） | 见下方 |
| `{{decisions}}` | 决策列表（数组） | 见下方 |
| `{{cost_rows}}` | Token 消耗明细（数组） | 见下方 |
| `{{surprises}}` | 发现列表（数组） | 见下方 |
| `{{debt_items}}` | 技术债务（数组） | 见下方 |
| `{{lessons}}` | 教训（数组） | 见下方 |

### 数组结构示例

**milestones:**
```json
{
  "name": "M1: Add constraint definitions",
  "status": "completed",
  "marker": "✓",
  "date": "2026-07-24",
  "duration": "2h",
  "test_result": "VERIFIED"
}
```

**decisions:**
```json
{
  "title": "Use worktree for isolation",
  "tier": "tier-c",
  "rationale": "Sequential dependent agents need shared filesystem",
  "source": "docs/adr/0003-worktree-isolation.md"
}
```

**cost_rows:**
```json
[
  {"source": "P 代理初始化", "tokens": "30,212", "note": "首次生成，实测值", "highlight": false},
  {"source": "E 代理初始化", "tokens": "20,226", "note": "首次生成，实测值", "highlight": false},
  {"source": "V 代理初始化", "tokens": "31,572", "note": "首次生成，实测值", "highlight": false},
  {"source": "合计（估算）", "tokens": "~650,000", "note": "±30% 误差范围", "highlight": true}
]
```

---

## 与 ExecPlan 集成

在 `docs/PLANS.md` 模板中添加：

```markdown
## Completion Checklist

- [ ] 所有里程碑已完成并验证
- [ ] Outcomes & Retrospective 已撰写
- [ ] **执行报告已生成** (`docs/exec-plans/reports/<plan-id>-report.html`)
- [ ] 报告中包含：
  - [ ] 里程碑时间线
  - [ ] Tier C 决策总结
  - [ ] 技术债务清单
  - [ ] 经验教训
```

---

## 示例输出

生成的报告将包含：
1. **顶部仪表板**：4 个关键指标，一眼看清计划健康度
2. **里程碑时间线**：每个 M 的完成状态、耗时、验证结果
3. **关键决策**：Tier C 决策高亮显示，待办决策警告框
4. **Surprises**：意外发现的分类展示
5. **技术债务**：按严重程度排序的债务清单
6. **经验教训**：可提升为规则的建议

---

## 自定义样式

如需调整样式，编辑 `.claude/templates/plan-execution-report.html` 中的 CSS 变量：

```css
:root {
  --color-success: #10b981;  /* 成功绿 */
  --color-warning: #f59e0b;  /* 警告黄 */
  --color-danger: #ef4444;   /* 危险红 */
  --color-info: #3b82f6;     /* 信息蓝 */
}
```
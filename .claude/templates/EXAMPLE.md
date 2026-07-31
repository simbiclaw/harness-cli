# Plan Execution Report 生成示例

## 场景
计划 9005 已完成，需要生成执行报告。

## 你的提示（复制粘贴即可）

```
计划 9005 已完成，生成执行报告。

模板：`.claude/templates/plan-execution-report.html`
输出：`docs/exec-plans/reports/9005-report.html`

数据：
- Plan 文件：`docs/exec-plans/completed/9005-pev-loop-evolution.md`
- 验证记录：`.claude/verification/9005/`
- 实现笔记：`.claude/implementation-notes/9005.md`

要求：
1. 提取所有里程碑（M1-M10）及状态
2. 提取所有 Tier C 决策（标记为 tier-c 样式）
3. 提取 Surprises 和 Lessons Learned
4. 计算健康度：（完成里程碑数 / 总里程碑数）* 100
5. 使用 playground skill 渲染 HTML
6. 确保待办决策显示警告框

报告风格：
- 顶部 4 个指标卡（健康度、里程碑、决策、验证）
- 左侧时间线，右侧决策
- 底部通栏：Surprises、技术债务、教训
```

## 生成的报告预览

报告将包含以下部分：

### 顶部仪表板
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Plan Health │ Milestones  │ Tier C      │ Verification│
│    100%     │  10/10      │     2       │    10       │
│   (green)   │  (green)    │  (yellow)   │  (green)    │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

### 左侧：里程碑时间线
- M1: ✓ Add constraint definitions (2026-07-24, 2h, VERIFIED)
- M2: ✓ Pre-execution constraint gate (2026-07-24, 3h, VERIFIED)
- ...

### 右侧：关键决策
- [黄色高亮] Tier C: Use worktree for isolation
  Rationale: Sequential dependent agents need shared filesystem
  
- [蓝色] Use YAML for constraints
  Rationale: Human-readable, machine-parseable

### 底部通栏
**Surprises:**
- ⚠️ Warning: Hook cannot trigger skill (discovered M3)

**Technical Debt:**
- [medium] Worktree cleanup logic needs refactor

**Lessons Learned:**
- ⬆️ Promotion Candidate: PEV checkbox-flip gate

---

## 快速调用（极简版）

如果你已经很熟悉流程，只需说：

```
为计划 9005 生成执行报告，使用模板。
```

系统会自动：
1. 读取模板 `.claude/templates/plan-execution-report.html`
2. 从 `docs/exec-plans/completed/9005*.md` 提取数据
3. 生成 `docs/exec-plans/reports/9005-report.html`
4. 在 Outcomes 中添加链接

---

## 注意事项

1. **必须在计划移至 completed/ 后生成** — 确保所有数据完整
2. **健康度计算**：(已完成里程碑 / 总里程碑) * 100
3. **Tier C 决策**：必须在 Decision Log 中标记
4. **验证状态**：从 `.claude/verification/` 读取对抗验证结果

## 文件位置

```
.claude/
├── templates/
│   ├── plan-execution-report.html    # 模板文件
│   └── README.md                      # 使用指南
└── reports/  (生成后)
    └── 9005-report.html
```
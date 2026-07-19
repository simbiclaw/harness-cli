# INTENTS — Agent Routing Index

## 如何浏览这棵树

路径即本体。每个目录节点下有一个 `intent_manifest.json`。
`find INTENTS -name "intent_manifest.json"` 找到全部。

manifest 中:
  `source`          — doc2graph | audio2tree | both
  `calibration_status` — calibrated | needs_manual | needs_calls | conflict
  `top_down`        — Doc2Graph 写入 (手册引用, 算子数, 目标态)
  `bottom_up`       — audio2tree 写入 (通话数, 聚类质心, channel, status)
  `description`     — L1/L2 的语义锚点, 必须有对比边界

## 路由协议 (audio2tree Consumer)

1. 提取通话 Request (S1)
2. 向量化 Request
3. 对所有 L2.description 计算余弦相似度:
   - L2 描述从 intent_manifest.json 提取, 非本文件重复
   - `find INTENTS -path "*/L2/*/intent_manifest.json" -exec jq -r '"\(.intent_id)\t\(.description)"' {} \;`
4. S_max >= 0.60 → 匹配通道 (L2 约束下 L3 聚类)
5. S_max < 0.60  → 偏差通道 (自动 L2 聚类 + 命名)
6. L2 数量 > 50/L1 → 启用 neighborhood 分治

## 读取协议 (Argus Evaluator)

1. 从 AGENTS.md 和 manifest.json 确认通话归属的 L1/L2/L3
2. `cat INTENTS/<L1>/<L2>/<L3>/intent_manifest.json` → top_down + bottom_up
3. `find INTENTS/_rubric/rules_criteria/` → 对应维度的编译 Item
4. manifest.source == "audio2tree": 手册引用信号返回 deferred
5. manifest 存在但 _rubric 无 Item: 该 L2 仅作路由标签，不评分

## 写入规则

- 不直接写。所有变更通过 transformation layer (audio2tree, doc2graph，criteria-compiler,navigator)
- 每个文件由单一生产者拥有 (_meta/ownership.yaml)
- 稳定 intent_id 一旦分配，不可修改 (即使重命名中文标题)

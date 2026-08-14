# AR 实验台账 (autoresearch 阶段1 人审闭环)

> 规则见 docs/autoresearch-spec.md
> 判定: keep = hit_rate ≥ 基线+0.02 且 I1-I4 全绿 且 延迟/调用数 ≤1.5×基线

## 基线 (v1.0)
avg_hit_rate = **0.723** (见 ar-baseline.md, 数据 golden_baseline_20260814.json)

## 实验记录

### AR-01: system_prompt v1.1 — 结论先行 + 分点完整展开 [DISCARD]
- 改动: compliance_qa.py system_prompt 增加规则5 (结论先行/逐项列全)
- 假设: golden 期望要点是法规概念词, "逐项列全"提高覆盖而不牺牲"不编造"
- 结果: avg 0.734 vs 基线 0.723 → **delta +0.011 < +0.02 阈值**
- 不变量: I1 ✓ (3 passed) I2 ✓ (audit_reconstruct OK) I3 ✓ (191 passed) I4 ✓ (无孤儿)
- 判定: **DISCARD** (无显著改进, 已还原 v1.0)
- 教训: 该改动方向 (结构化输出) 收益有限 — 低命中题根因是 guard 拦截/检索覆盖, 非 prompt 结构

### AR-02 (候选, 未执行): intent guard 误伤
- 现象: "大模型服务提供者有哪些义务？" (合法事实查询) 被 guard 快速拒绝 30ms/33%
- 方向: 检查 classify_intent 关键词误判, 需先建误伤率样本集

## AR-02: intent guard 误伤 (2026-08-14)

- **发现**: golden 基线第 23 题 "AI模型备案和算法备案有什么区别?" 被判 meta 拒绝 (meta_kw "有什么区别" 过宽) — 合规概念对比被误认为元问题
- **样本集**: data/intent_guard_samples.json (20 条合法事实查询, 覆盖义务/对比/豁免/否定/主体/流程/跨境)
- **修复**: "区别" 类仅在对系统/模型提问时判 meta (含 你/chatgpt/你们/系统), 其余 "区别" → factual
- **验证**: 样本集 20/20 factual; golden 30 题误伤 1→0; meta 6 例不回归; 注入/角色扮演/探测 3 例仍拦截
- **门禁**: tests/test_intent_guard.py (4 测试, 防回退)
- **AR-02 结论**: DONE (误伤率样本集 0/20, golden 0/30)

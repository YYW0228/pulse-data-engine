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

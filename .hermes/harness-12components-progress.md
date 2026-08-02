# 中国企业版 Agent Harness — 12 组件落地进度 (2026-08-02)

> 更新于: 2026-08-02 (合规问答助手阶段)
> 关联: harness-cn-deep-dive.md (v1.0) + harness-cn-exploration-v1.1.md
> 铁律: 未来证明测试贯穿 — 模型变强时 Harness 应变简单, 变复杂=设计有问题

## 12 组件状态

| # | 组件 | 状态 | 实现位置 |
|---|------|------|---------|
| 1 | Orchestration Loop | ✅ | pulse/dag.py + assets.py |
| 2 | Tools | ✅ | fetcher.py + fetchers/scrapling_fetcher.py |
| 3 | Memory | ✅ | compliance.duckdb 向量库 |
| 4 | Context Management | ✅ | scripts/compliance_qa.py (Context Compiler) |
| 5 | Prompt Construction | ✅ | compliance_qa.py (中文合规+强制引用) |
| 6 | Output Parsing | ⚠️ | Pipeline Pydantic 有, 合规问答未强制结构化 |
| 7 | State Management | ✅ | DAG 状态 + dag_runs + plan.md |
| 8 | Error Handling | ✅ | Circuit Breaker + DLQ |
| 9 | Guardrails | ✅ | Data Contract + 对抗验证 6/6 |
| 10 | Verification Loops | ✅ | 三层对账 + SLA + 引用校验 |
| 11 | Subagent | ⬜ | delegate_task 可用, 未接入 |
| 12 | Observability | ✅ | compliance_metrics + Prometheus |

## 高优四件套基线 (实测数据)

```
Context Management:  相似度 0.698 (raw 0.675) | 文档 2.9 (raw 4.9) | 127ms (raw 1033ms)
Guardrails:          对抗验证 6/6 (幻觉/越权/误导/边界/数据最小化)
Verification:        引用规则强化后 13-18 处/题 (弱规则时 4/10 题 0 引用)
Observability:       $0.0009/问答 | 1532tok→459tok | 7 引用 | 100% 成功率
```

## 下一步待办 (按 prompt 落地路径)

1. **Output Parsing 强化** — 合规问答强制 Pydantic 结构化输出 (JSON mode)
2. **trace + replay** — 记录每步 (检索→编译→回答), 支持回放调试
3. **cost-aware 路由** — 简单问题用小模型/规则, 复杂用大模型 (动态模型选择)
4. **记忆一致性** — 向量库加版本/冲突检测/遗忘策略
5. **Meta-Loop 自优化** — 失败轨迹 → 自动生成 prompt/策略修改提案 → 沙箱 A/B
6. **审批流** — 高风险操作人工确认 (人机协同从提醒→审批)

## 方向检查标准

- 是否还在"阶段1 单场景扎实 → 阶段2 可观测"路径上? (是=继续, 否=纠偏)
- 每个新组件过未来证明测试: 模型变强时此组件变简单?
- 每个改动附带评测数据 (不 vibecoding)

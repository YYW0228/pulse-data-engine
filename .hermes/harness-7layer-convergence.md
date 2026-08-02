# 七层极简全栈 — 中国企业版 Agent Harness 收敛骨架 (2026-08-02)

> 版本: v2.0 (由 12 组件 v1.0 收敛而来)
> 决策: 7 层为对外骨架, 12 组件保留为内部检查清单
> 关联: harness-cn-deep-dive.md (12 组件 v1.0) + harness-cn-exploration-v1.1.md

## 七层骨架 (横向贯穿: Guardrails + Observability)

```
1. Surface    — 入口层: 多入口归一成统一 Task Object
2. Orchestration — 编排层: 薄循环 plan→read/write/check→merge→answer
3. Context    — 上下文层: "window is a budget, not a bucket" 强制 compact
4. Model      — 模型层: 小模型 80%+ 常规, frontier 仅关键路径
5. Tools      — 工具层: 可见即存在, 白名单 + 完整 schema
6. Runtime    — 运行时层: 沙箱墙是特性, 隔离/保护/日志
7. Memory     — 记忆层: write it down or watch it evaporate
```

## 12 组件 → 7 层精确映射

| 7 层 | 对应 12 组件 | 中国企业版强化 | 未来证明 |
|-----------|-------------|--------------|---------|
| 1. Surface | Prompt Construction + 入口适配 | 统一 Task Object, 屏蔽钉钉/飞书/OA/API 差异 | 几乎不变 |
| 2. Orchestration | Orchestration Loop + Subagent + Verification(部分) | 薄循环 + fan-out/merge + 内嵌验证 | 应变薄 |
| 3. Context | Context Management + Prompt 组装 | Budget 思维, 强制 compact / observation masking | 应变薄 |
| 4. Model | (隐含) + 新增路由 | 小模型默认 + 复杂度/置信度升级 | 路由可变简单 |
| 5. Tools | Tools + Output Parsing(工具调用) | 白名单 + schema 可见性 + 沙箱执行 | 几乎不变 |
| 6. Runtime | State + Error Handling + Guardrails(执行) | 沙箱墙是特性; 权限/隔离/日志/重试 | 几乎不变 |
| 7. Memory | Memory + State(持久化) | 显式 write-it-down; 多级 + 可审计 | 可部分简化 |
| 横向 Guardrails | Guardrails + Verification Loops | 输入/工具/输出三道闸 | 规则可内化, 策略保留 |
| 横向 Observability | Lifecycle + Observability | 全链路 Trace/成本归因/失败聚类/审计 | 必须保留加强 |

## 当前实现的 7 层映射

```
Surface:    Streamlit 前端 + CLI (compliance_qa.py) — 待归一 Task Object
Orchestration: DAG 状态机 + 检索→编译→回答循环 ✅
Context:    Context Compiler (预算思维已实现) ✅
Model:      DeepSeek 单一模型 — 待加路由层 ⬜
Tools:      Fetcher v2 + Scrapling 适配器 ✅
Runtime:    systemd 沙箱 + 端口隔离 + 审计日志 ✅ (部分)
Memory:     compliance.duckdb 向量库 + metrics JSONL ✅
Guardrails: Data Contract + 对抗验证 6/6 + 注入防御 0/8 ✅
Observability: compliance_metrics + Prometheus ✅
```

## 未来证明测试升级版

1. 模型变强后 Harness 变简单? (原版)
2. **换模型 (Claude→Kimi/本地) 需要改动的层尽量少?** (新增)
   - 判断: 改 Surface? 错 (入口与模型无关)
   - 改 Model 路由层? 对 (唯一应改的层)
   - 改 Context/Tools/Runtime? 错 (应与模型无关)

## 平台化路径微调

```
原: 单场景 → Runtime → 工具注册中心 → 多租户 → 多Agent
微调: 先把单场景 7 层跑通 (Verification 嵌入 Orchestration,
      Error Handling 嵌入 Runtime), 再做统一 Runtime + 工具注册中心,
      最后才考虑多 agent fan-out
```

## 核心指令 (归档)

"采用七层极简全栈 (Surface → Orchestration → Context → Model → Tools → Runtime → Memory, 外加横向 Guardrails & Observability), 把 12 组件收敛映射到这 7 层上, 优先保证薄而可控, 拒绝框架绑架。"

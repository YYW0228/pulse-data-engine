# Pulse Data Engine — Architecture

> 审核合入: Hermes (2026-08-31) — 草稿由 VPS pi 依据 CONTEXT.md 术语表 + 代码结构重建
> 审核方式: 代码抽查核对 (8 核心模块存在性 / compliance_qa 1266 行 / pipeline.py SCD2 函数) — 全部通过
> 状态: **ACTIVE** (2026-08-31 合入, 替代 DRAFT)
> 源草稿: agent-bus/artifacts/report/pulse-architecture-draft.md (P4)

## 1. 定位

轻量数据管道引擎: 多公开 API 采集职位数据 → Pydantic Data Contract 校验 → DuckDB 三层数仓 (ODS→DWD→DWS) → Iceberg time travel + SQL 浏览器查询。兼作 Agent 治理基座 (finops 核算 / LLM 审计 / agent-bus 消息总线 / 8502 问答)。

## 2. 数据架构 (三层 medallion + 死信)

```
外部 API (boss/shopify_mock/jobicy/dap_enrich)
        │  fetcher.py (电路断路器/退避/重试)
        ▼
  validate_and_route()  ← Data Contract (Pydantic v2)
   ├─ pass → merge_into_ods()      ODS (append-only, SCD Type 2, is_latest 标记)
   ├─ fail → write_dlq()           DLQ (可放宽契约后重放)
   └─ 清洗去重 → DWD (每实体一行, 最新版本)
              → DWS (预聚合: 薪资分位/技能/城市)
        │
        ▼
  Parquet 导出 (iceberg 快照) → wasm_server (CORS+Range) → DuckDB WASM 浏览器查询
```

- 数据契约 (schema.py/contracts/): 每条记录入 ODS 前强校验, 违反→DLQ; 非存量质检
- SCD Type 2 (pipeline.py): URL hash 为实体键, salary/title/city 变化开新行

## 3. 组件清单 (pulse/)

| 模块 | 职责 |
|---|---|
| pipeline.py | 三层数仓管道 v4: validate_and_route / merge_into_ods (SCD2) / DLQ |
| dag.py | 轻量 DAG 编排: @task 注册/拓扑排序/失败下游终止/重试+backoff, 状态存 DuckDB dag_runs |
| fetcher.py | 工业抓取层: 电路断路器 / full jitter 退避 / Retry-After / 自适应超时 |
| extractors/ | 适配器层 (boss/shopify_mock/jobicy/dap_enrich), 无状态 |
| schema.py + contracts/ | Data Contract (Pydantic v2) + 领域契约 |
| finops.py | Agent 成本核算 (wanman 移植): cost model / ledger / pricing registry |
| llm_audit.py | model-visible=logged 不变量: 请求前落盘, data/llm_audit.jsonl 可重建 |
| vector_store.py | 向量存储抽象 (DuckDB VSS / Qdrant 可换) |
| wasm_server.py | 本地 Parquet HTTP 服务器 (模拟 CF Worker CORS+Range) |
| agent_bus.py | 三 agent 消息总线 (inbox/artifacts/replies/context/tasks) |
| metrics_server.py / monitor.py / backup.py / checkpoints.py / trace.py | 运维支撑 |

## 4. 脚本层 (scripts/)

compliance_qa (1266 行, 合规质检) / kb_refresh (296 行) / vas_goal / backup_health / analyze_runs / audit_reconstruct / boss_fetcher / check_goal / alert_check / compliance_index / adapter_scaffold / adversarial_eval / answer_quality_eval …

## 5. 关键运行不变量

1. **Data Contract 前置**: 违反不落 ODS, 进 DLQ
2. **SCD2 版本化**: is_latest 标记活跃版本, 时间旅行看历史
3. **DAG 幂等**: dag_runs 持久化, 失败可恢复
4. **model-visible = logged**: LLM 请求全量落盘 (llm_audit)
5. **8502 问答**: DWS 层 + 知识库 → 问答服务

## 6. 技术栈

uv / Python 3.10+ / DuckDB (热) + Parquet (冷) / Pydantic v2 / Iceberg / Dagster 语义 (Asset) / Cloudflare 部署面 (零计算 $0/月 目标)

## 7. 边界

- 镜像仓 (VPS): 只读; 权威运行在 Mac mini (7×24)
- 生产红线: DuckDB 不跨机; git 唯一同步; pi 禁写 8502

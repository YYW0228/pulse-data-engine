# 吞噬成果映射回 7 层骨架 + 迭代配置 (2026-08-05 更新)

> 目的: 把 harness-devour 吞噬的模式映射回项目架构 + 主线各仓库,
>       让每一轮吞噬都沉淀为架构能力。v2: 22 模式全量映射 + 主线仓库回向。

---

## 一、22 个模式 → 7 层映射 (v2 全量)

| 7 层 | 吞噬模式 (状态) | 落地位置 | 价值 |
|------|---------|---------|------|
| **Surface** | evidence_artifacts ✅ (Kun) | pulse/artifacts.py | 证据包可验收 |
| **Surface** | handoff_summary ✅ (buzz) | compile_context 交接摘要 | 状态不丢 |
| **Orchestration** | loop_detection ✅ (DeerFlow) | compliance_qa.py _loop_detector | 状态漂移防御 |
| **Orchestration** | turn_metric_semantics ✅ (buzz) | metrics 回合指标 | 指标语义严谨 |
| **Context** | reactive_compaction ✅ (mini-claude-code) | compile_context 大块转存 + 反应式重试 | 长上下文不炸 |
| **Context** | prefix_cache_stability ✅ (Reasonix) | system_prompt 版本化 + append-only | 成本自动优化 |
| **Model** | prefix_cache_stability (同上) | 路由层 + 稳定前缀 | 换模型少改 |
| **Runtime** | token_budget ✅ (DeerFlow) | answer(budget=) 闸门 | 成本硬闸门 |
| **Memory** | memory_extract_consolidate ✅ (mini-claude-code) | MemoryStore extract+consolidate | 记忆自动沉淀 |
| **Guardrails** | identity_scoping 👀 (buzz) | 观察中 (身份隔离) | 多租户安全 |
| **Tools** | mcp_tool_exposure 🧪 (browser-use/scrapling) | dap/mcp_server.py | Agent 可调 |
| **Tools** | fetcher_escalation_ladder 🧪 (Scrapling) | dap/fetchers/ladder.py | 反爬升级 |
| **Tools** | browser_action_registry 🧪 (browser-use) | dap/interact/actions.py | 交互原语 |
| **Tools** | proxy_pool_rotation 🧪 (自研) | dap/fetchers/proxy_rotator.py | IP 封锁 |
| **Tools** | cloudflare_turnstile_solver 🧪 (Scrapling) | dap/fetchers/browser_fetcher.py | CF 绕过 |
| **Evidence** | field_level_source_grounding ✅ (langextract) | dap/extractors/aligner.py | 字段溯源 |
| **Evidence** | link_to_citation_grounding 🧪 (crawl4ai) | dap/extractors/markdown_gen.py | 链接溯源 |
| **Cost** | information_foraging_saturation 🧪 (crawl4ai) | dap/foraging/saturation.py | 先诊断再花token |
| **Cost** | status_code_adaptive_ratelimit 🧪 (crawl4ai) | dap/throttle.py | 状态码退避 |
| **Sandbox** | sandbox_worker_pool 👀 (boxsh) | 观察中 | 进程隔离 |
| **Sandbox** | cow_workspace 👀 (boxsh) | 观察中 | COW 写隔离 |
| **Memory** | selflearn_memory 👀 (San) | 观察中 | 自进化记忆 |

## 二、主线仓库回向映射 (吞噬成果 → 各仓库)

| 主线仓库 | 已落地的吞噬模式 | 文件 | 状态 |
|---------|----------------|------|------|
| **pulse-data-engine** (合规问答引擎) | evidence_artifacts / loop_detection / reactive_compaction / prefix_cache / token_budget / memory_extract / handoff_summary / turn_metric_semantics | pulse/artifacts.py, compliance_qa.py, MemoryStore | ✅ 8 模式 |
| **pulse-data-engine** (数据管道) | dap_enrich (字段溯源+信息觅食) | pulse/extractors/dap_enrich.py, runner.py | ✅ 2 模式 |
| **pulse-data-engine** (boom 爆款) | factor_evidence (字段溯源) | pulse/extractors/boom/analyzer.py, boom_pipeline.py | ✅ 1 模式 |
| **china-ai-governance** (合规情报) | fetcher_escalation_ladder / link_to_citation / ratelimit / proxy_pool | scripts/intel-pipeline/dap_fetch.py, intel_pipeline_dap.py, _intel_scraper_v2.py | ✅ 4 模式 |
| **startalent-enterprise** | (待映射) | — | ⚠️ 未接入 |
| **hermes-brain** | (待映射) | — | ⚠️ 未接入 |
| **job-scraper** | (待映射) | — | ⚠️ 未接入 |

## 三、迭代节奏 (吞噬 → 映射 → 配置)

```
吞噬 (雷达白名单) → 评分 (CI 门禁) → 裁决 (双过滤)
→ 落地 (实验→合入) → 映射 (本文档) → 配置 (metrics/trace)
→ 观测 (面板) → 下一轮
```

## 四、watch 模式升级条件 (观察→迁移)

| watch 模式 | 升级触发条件 |
|-----------|-------------|
| middleware_chain | 关注点 > 10 (Rule of Three) |
| selflearn_memory | 真实长任务数据积累 (试点后) |
| sandbox_worker_pool | 请求级超时隔离需求 (高并发) |
| cow_workspace | 客户文件安全卖点确认 |
| identity_scoping | 多客户试点 (数据隔离需求) |

## 五、当前架构能力全景 (7层 × 吞噬累积, 2026-08-05)

```
Surface:   Task Object + 证据包 (Kun) + 意图分类 + 交接摘要 (buzz)
Orchestration: DAG + loop_detection (DeerFlow) + capped 终止 + 回合指标 (buzz)
Context:   Compiler + MMR + 大块转存 + 反应式压缩 (mini-claude-code)
Model:     路由层 + prefix-cache 稳定 (Reasonix)
Tools:     白名单 + 四级升级链 (Scrapling) + 交互原语 (browser-use) + MCP + 代理池
Runtime:   systemd + token_budget (DeerFlow) + 空回答重试
Memory:    WAL + 冲突 + 遗忘 + 提取 + 合并 (mini-claude-code)
Evidence:  证据包 (Kun) + 字段级溯源 (langextract) + 链接引文 (crawl4ai)
Cost:      缓存稳定 (Reasonix) + 预算闸门 (DeerFlow) + 信息觅食 (crawl4ai) + 状态码退避
Sandbox:   worker_pool / cow_workspace (观察中)
Guardrails: 意图 + 注入 + loop + 预算 + 对抗 + 身份隔离 (观察中)
Observability: metrics + trace + cache_hit_rate + 成本面板 + 溯源字段
```

## 六、信息管道全景 (2026-08-05 升级)

```
┌─ 管道 1: 法规情报 (china-ai-governance) ← dap 升级链 v2
│   intel_scraper_v2 (每日04:00, dap 四级升级+多源回退) → kb_refresh → compliance.duckdb
│   实测: Reddit IP限流 → 法规源 34 条真实情报 + 引文溯源
│
├─ 管道 2: 市场洞察 (job-scraper)
│   CI 每周2次 → collector.py → jobs.duckdb → market_knowledge/ → 知识库
│
├─ 管道 3: 客户专属 (customer_onboard)
│   raw/ → 独立库 → 8502 切换
│
└─ 管道 4: 爆款监控 (boom) ← dap 字段溯源 v2
    TikHub → boom.duckdb → L1 分析 (factor_evidence 溯源)

知识库 487 块 = 法规 287 + 情报 191 + 市场 4 + 客户 (独立)
三出口: 合规问答 8502 / 直播 Dashboard / 销售报告
```

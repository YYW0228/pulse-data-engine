# 吞噬成果映射回 7 层骨架 + 迭代配置 (2026-08-03)

> 目的: 把 harness-devour 吞噬的 6 个 migrated 模式映射回项目架构,
>       更新迭代配置, 让每一轮吞噬都沉淀为架构能力。

---

## 一、6 个 migrated 模式 → 7 层映射

| 7 层 | 吞噬模式 | 落地位置 | 价值 |
|------|---------|---------|------|
| **Surface** | evidence_artifacts (Kun) | pulse/artifacts.py | 证据包可验收 |
| **Orchestration** | loop_detection (DeerFlow) | compliance_qa.py _loop_detector | 状态漂移防御 |
| **Context** | reactive_compaction (mini-claude-code) | compile_context 大块转存 + 反应式重试 | 长上下文不炸 |
| **Model** | prefix_cache_stability (Reasonix) | system_prompt 版本化 + append-only | 成本自动优化 |
| **Runtime** | token_budget (DeerFlow) | answer(budget=) 闸门 | 成本硬闸门 |
| **Memory** | memory_extract_consolidate (mini-claude-code) | MemoryStore extract+consolidate | 记忆自动沉淀 |
| **Guardrails** | loop_detection (重复部分) | loop_capped 终止 | 循环防御 |

## 二、12 组件进度更新

| 组件 | 之前 | 现在 | 吞噬来源 |
|------|------|------|---------|
| 3. Memory | ✅ WAL/冲突/遗忘 | ✅ +提取+合并 (5机制) | mini-claude-code s09 |
| 4. Context | ✅ 预算+MMR | ✅ +大块转存+反应式 | mini-claude-code s08 |
| 8. Error Handling | ✅ 空回答重试 | ✅ +prompt_too_long 压缩重试 | mini-claude-code s08 |
| 9. Guardrails | ✅ 意图+注入 | ✅ +loop_capped+预算闸门 | DeerFlow |
| 10. Verification | ✅ 引用+对抗 | ✅ +证据包 (可验收) | Kun |

## 三、迭代配置 (可观测/评测)

### 新增评测项
```
1. 缓存命中率 (cache_hit_rate) — 已在 metrics ✅
2. 压缩触发率 (reactive_compact 次数) — trace 有, metrics 待加
3. 合并去重率 (consolidate 删除条数) — memory demo 有
4. 证据包产出率 (artifact 生成数) — artifacts 目录计数
```

### 新增观测面板字段 (serve_compliance.py)
```
- 缓存命中率 (来自 summarize.cache_hit_rate)
- 压缩触发次数 (来自 trace reactive_compact 步)
```

## 四、迭代节奏 (吞噬 → 映射 → 配置)

```
吞噬 (雷达白名单) → 评分 (CI 门禁) → 裁决 (双过滤)
→ 落地 (实验→合入) → 映射 (本文档) → 配置 (metrics/trace)
→ 观测 (面板) → 下一轮
```

## 五、watch 模式升级条件 (观察→迁移)

| watch 模式 | 升级触发条件 |
|-----------|-------------|
| middleware_chain | 关注点 > 10 (Rule of Three) |
| selflearn_memory | 真实长任务数据积累 (试点后) |
| sandbox_worker_pool | 请求级超时隔离需求 (高并发) |
| cow_workspace | 客户文件安全卖点确认 |

## 六、当前架构能力全景 (7层 × 吞噬累积)

```
Surface:   Task Object + 证据包 (Kun) + 意图分类
Orchestration: DAG + loop_detection (DeerFlow) + capped 终止
Context:   Compiler + MMR + 大块转存 + 反应式压缩 (mini-claude-code)
Model:     路由层 + prefix-cache 稳定 (Reasonix)
Tools:     白名单 + read/write (观察)
Runtime:   systemd + token_budget (DeerFlow) + 空回答重试
Memory:    WAL + 冲突 + 遗忘 + 提取 + 合并 (mini-claude-code)
Guardrails: 意图 + 注入 + loop + 预算 + 对抗
Observability: metrics + trace + cache_hit_rate + 成本面板
```

## 七、信息管道全景 (2026-08-03 新增市场管道)

```
┌─ 管道 1: 法规情报 (china-ai-governance)
│   intel_scraper (每日04:00) → kb_refresh → compliance.duckdb
│   用途: 合规问答 + 知识保鲜 (护城河)
│
├─ 管道 2: 市场洞察 (job-scraper) ← 新增回流
│   CI 每周2次 → collector.py → jobs.duckdb (1043 岗)
│   → export_market_insight.py → markdown 报告
│   → data/market_knowledge/ → 索引 → 知识库 (4 块)
│   用途: 直播素材 + 销售话术 + 课程方向 + 市场问答
│   实测: "市场最缺什么AI人才" → AI治理 5 痛点居首, 带 JD 证据
│
└─ 管道 3: 客户专属 (customer_onboard)
    raw/ → 独立库 → 8502 切换
    用途: 试点交付 (数据隔离 + 检索质量)

知识库 483 块 = 法规 287 + 情报 + 市场 4 + 客户 (独立)
三出口: 合规问答 8502 / 直播 Dashboard / 销售报告
```

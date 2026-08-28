# 情报简报: harness-engineering

**时间**: 2026-08-27 16:12 UTC
**源**: Reddit r/LocalLLaMA / r/ClaudeAI / r/ChatGPTCoding
**说明**: 本轮 4 组搜索命中 30+ 帖；web_extract 仅 PAMPA 帖全文成功，其余被 Reddit 网络层拦截 → 标注"基于搜索摘要"。已与 2026-08-26 与 2026-08-27(04:09 UTC) 两份报告全面去重：Prime Agent、Hermes vs RLM、compaction 死循环、ContextSpy、SmallCode 87%、Same model 4 agents、Nous AMA、Maggy、Anthropic 官方 harness 定义、MCP 记忆层(1ueh2t0)、Claude Code context-engineering(1u9wuaq)、"my harness" 术语、Pi harness 辨析、RL train any agent(1m9m670) 等均不重复收录。

## 高相关度发现

- [88pts] **OmniCoder-9B：用 425K 条前沿 agent 轨迹微调的本地 coding agent（基于搜索摘要）** → 数据源为 Claude Opus 4.6 / GPT-5.4 / GPT-5.3-Codex / Gemini 3.1 Pro 的真实 agentic 轨迹，**目标脚手架模式来自 Claude Code / OpenCode / Codex / Droid**；262K 原生上下文（可扩 1M+）；从轨迹中学到 read-before-write、响应 LSP diagnostics、用最小 edit diff 而非整文件重写；Apache 2.0。意义：harness 行为模式正在被蒸馏进模型本身 — 我们七层骨架的纪律（读前写、PreToolUse 闸门、最小变更）正是前沿轨迹编码的行为，同时为本地栈提供可替换的 agent 基座候选。https://www.reddit.com/r/LocalLLaMA/comments/1rs6td4/omnicoder9b_9b_coding_agent_finetuned_on_425k
- [85pts] **Qwen3.6 + Hermes Agent 本地跑通实况（基于搜索摘要）** → 社区实战报告：Hermes 在 $50 i5-6500T 旧机、8845HS mini PC 均可跑；Pi 4B 慢；Nvidia 免费 API 层首 token 与速率"几乎不可用"；$20/mo Ollama Cloud Pro / MiniMax 订阅够用；4B 模型"灵巧、响应快、有活力"，Qwen3.5:9b 胜任更重任务；dense 模型适合 agentic/coding；反方声音"本地永远追不上前沿"。与我们 Hermes+Qwen 本地栈直接同构：验证低成本部署路径 + 订阅层定价数据点，也提示本地 vs 云端的期望管理。https://www.reddit.com/r/LocalLLaMA/comments/1so9tbq/testing_qwen36_with_hermes_agent_on_agentic
- [75pts] **PAMPA/pampax：代码记忆 MCP，reranker 从 75%→100% precision@1（全文已抓取，~10mo 首捕）** → embedding+reranker 代码库语义记忆 MCP；Laravel+TS 语料基准：Qwen3-Embedding-8B + 本地 transformers.js reranker ≈75%，+ Qwen3-Reranker-8B 达 100%；fork 增加任意 OpenAI 兼容端点、API reranker、>30KB 大文件索引修复。社区反证（本报告高价值）："记忆类 MCP 表面强大但 LLM 完全无视" — context7 挂默认数月从未被自发调用；作者承认"必须强制使用"，靠注入规则(RULE_FOR_PAMPAX_MCP.md)驱动；另有"工具太多模型直接摆烂"现象。直接指导我们 L2/L3 记忆设计：记忆查询应是显式强制协议而非可选工具。https://www.reddit.com/r/LocalLLaMA/comments/1oa1gz9/an_mcp_to_improve_your_coding_agent_with_better

## 中相关度

- [68pts] **本地 CLI coding agent 横向对比（基于搜索摘要）** → Claude Code 最受推荐但 Pro 限额"几乎不可用"；OpenCode 本地模型整合好但**初始 prompt 巨大导致 token 用量高**；Morph 实测：Claude Code 输出免人工修改率 78% vs Aider 71%，但 **Aider 省 4.2x token**。验收率与 token 效率的权衡数据点；初始 prompt 体积是隐性 token 成本 — 印证我们 L1 文件 150 行阈值与精简系统提示的设计。https://www.reddit.com/r/LocalLLaMA/comments/1swhw84/what_is_the_best_coding_agent_cli_like_claude
- [65pts] **Qwen Code + LM Studio 本地离线 agent 的现实（基于搜索摘要）** → qwen3-coder-30B 本地跑：默认 4096 ctx 连"hi"都处理不了（agent 要求 8k+）；开 Flash Attention + KV cache 量化推到 32k 后，**token 速度与代码质量双双显著下降**。本地 harness 扩窗的隐性质量代价实测 — 我们 llama.cpp 栈需量化 FA+KVCQ 对 agentic 质量的影响，勿盲目扩窗。https://www.reddit.com/r/LocalLLaMA/comments/1mtctda/trying_to_run_a_local_offline_coding_agent_with
- [45pts] **Local Coding Agent Help：8GB VRAM 硬下限（基于搜索摘要）** → RTX 4060 8GB 跑 OpenCode 本地模型生成 C# 应用持续失败；社区共识：16GB VRAM 才够 Q4 27B；ik_llama.cpp 3-4x 提速；llama.cpp 比 Ollama 快。本地 harness 部署的硬件地板信号。https://www.reddit.com/r/LocalLLaMA/comments/1rzx47w/local_coding_agent_help

## 趋势判断

前沿轨迹蒸馏进本地模型；记忆MCP需强制使用；token效率实测数据成标配。

---

### 最有价值 1 条

**OmniCoder-9B**（r/LocalLLaMA，1rs6td4）：9B 参数模型直接以 Claude Code/Codex/OpenCode/Droid 的脚手架模式为目标、用 425K 条前沿 agent 轨迹微调，学会了 read-before-write、LSP diagnostics 响应与最小 edit diff — 这验证了一个对我们是战略性的判断：**harness 的行为纪律正在变成训练数据**，scaffolding 的价值可以固化进模型权重，且 262K 原生上下文、Apache 2.0 完全适配本地栈。行动项：(1) 把 OmniCoder-9B 纳入 sovereign-singularity 本地 agent 基座评测矩阵，与 Qwen2.5-Coder-32B 对照；(2) 启动我们自己的成功轨迹采集（PostToolUse 管道天然产出行数据），为未来轨迹级微调/评估留存语料；(3) 其"最小 edit diff"与 read-before-write 行为可作为我们七层骨架行为规范的业界验证锚点。

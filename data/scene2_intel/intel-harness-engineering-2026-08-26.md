# 情报简报: harness-engineering

**时间**: 2026-08-26 16:14 UTC
**源**: Reddit r/LocalLLaMA / r/ClaudeAI / r/ChatGPTCoding
**说明**: web_extract 仅 Prime Agent 1 篇全文成功，其余被 Reddit 反爬网络层拦截 → 主要基于搜索标题+摘要（标注 "基于搜索摘要"）。本域首次报告，无历史去重。

## 高相关度发现

- [95pts] **Prime Agent — Prime Intellect 开源自改进 RLM harness（全文已抓取）** → 直接对标信号：context-as-variable、程序化工具调用、多 agent 消息、自修改 harness 状态；ARC-AGI-3 95.5%（Opus5 best-of-3）。社区反证：openbench 固定模型 deepseek-v4-flash 下，Prime Agent 8/8 任务耗 4.17M tokens vs 对照 harness 2.06M — **同分 2 倍成本**，自修改对非前沿模型无效。对我们的价值：我们正是 deepseek-v4-flash + Hermes 本地栈，token 经济性需实测而非信 benchmark。https://www.reddit.com/r/LocalLLaMA/comments/1vgnmny/prime_agent_a_new_coding_harness_surpassing（GitHub: PrimeIntellect-ai/prime-agent）
- [90pts] **Hermes Agent vs Recursive Language Model 争论（基于搜索摘要）** → RLM（arxiv 2512.24601, Alex Zhang/Prime Intellect）主张：context 是 on-heap 变量，模型主动把上下文委派给 Python 脚本/子 LLM，永不摘要（无信息损失），可 10M+ tokens 扩展，RL 端到端训练 context folding 是长 horizon 下一突破；OP 认为 Nous 把 RLM 当"复杂化 subagent"，subagent≠RLM。对我们：Hermes 七层骨架的 context 管理哲学需要明确站队。https://www.reddit.com/r/LocalLLaMA/comments/1rtnjki/hermes_agent_recursive_language_models
- [85pts] **Hermes Agent/Openclaw compaction 死循环 bug 报告（基于搜索摘要）** → Qwen3.5-27B + 262k ctx：触顶→compaction→从零重来→再触顶→无限循环且不再响应；降到 128k 无效。这是我们主线 harness 的直接稳定性风险信号，需在本机复现/规避。评论区："工具调用尽早规划 policy+audit，后期改造痛苦" — 印证我们的 PreToolUse 闸门设计。https://old.reddit.com/r/LocalLLaMA/comments/1s99y6z/hermes_agent_openclaw_context_compaction_loop
- [80pts] **本地 35B 平 GPT-5 Mini on SWE-bench Verified（基于搜索摘要）** → Qwen3.6-35BA3B + mini-swe-agent（~100 行框架，无微调）≈ 前沿小模型；教训：scaffolding 与模型能力归因分裂（"agent 的功劳大部分在 scaffolding" vs "大部分在模型本身"）；P40 46tok/s 下 thinking mode 单步 10 万 reasoning tokens = 40 分钟/步 → 本地 harness 必须管理 thinking budget。https://www.reddit.com/r/LocalLLaMA/comments/1sqrct4/matching_gpt5_mini_on_swebench_verified_with_a
- [75pts] **Claude Code 是 context-engineering harness + 抗 compaction MCP 记忆层（基于搜索摘要）** → 磁盘态状态每次会话重载故 survives compaction；MCP memory 层在 compaction 后按置信度重注入事实，避免跨会话重犯同一失败。对我们的 compaction 策略 = 落地参考。https://www.reddit.com/r/ClaudeAI/comments/1u9wuaq/claude_code_is_a_contextengineering_harness_and ; https://www.reddit.com/r/ClaudeAI/comments/1ueh2t0/built_an_mcp_memory_layer_for_claude_code_that

## 中相关度

- [70pts] **ContextBench：coding agent 上下文收集评测基准** → 测 agent 从代码库 gather context 的能力，harness 评测新基准，可纳入我们的 agent eval 矩阵。https://www.reddit.com/r/LocalLLaMA/comments/1u21vgq/benchmarking_coding_agent_memory
- [65pts] **Manus 后端 lead：把 AST 挂载为文件系统** → agent 用 ls/cat 导航代码，规避 context 爆炸；低门槛高收益的 context 工程技巧。https://www.reddit.com/r/LocalLLaMA/comments/1rrisqn/i_was_backend_lead_at_manus_after_building_agents
- [65pts] **Coding agent 浪费一半 context window** → mermaid 依赖图文档化可显著降 token；Context Engineering 工作坊聚焦确定性记忆。https://www.reddit.com/r/LocalLLaMA/comments/1rr5fo5/why_ai_coding_agents_waste_half_their_context
- [60pts] **Web-use harness 30x token 缩减、12x TTFT 缩减** → CDP 连接 + DOM→markdown 压缩，GitHub 上 32x token 缩减，18 工具，任意 tool-calling 模型可用；web 层 token 效率模板。https://old.reddit.com/r/LocalLLaMA/comments/1s5von5/web_use_agent_harness_w_30x_token_reduction_12x
- [60pts] **构建 agent 的 canonical 工程清单** → ① 持久化 schema 与 LLM schema 解耦、tool result 精简为最小必要 ② context manager 决定窗口取舍 ③ tool def = JSON schema + 执行函数 ④ 可选 pre-planning/post-reflection；硬问题：context 管理/错误恢复/多 agent 状态共享；参照 Aider 文档 + OpenAI Build Hour on Agent Memory。https://www.reddit.com/r/LocalLLaMA/comments/1s2kl1u/why_is_there_no_serious_resource_on_building_an
- [55pts] **给 SKILL 包写 eval harness** → 2 个月实践：对 RAG/agent/MCP 工作强制方法学严谨性；技能质量回归测试方法论。https://www.reddit.com/r/ClaudeAI/comments/1u6f7cr/what_i_learned_writing_an_eval_harness_for_my_own
- [55pts] **"Agent environment engineering" ≠ "Agent Harness"** → 环境工程=沙箱/状态/可观测性，harness=循环/工具/上下文；术语边界讨论，助我们内部架构文档对齐。https://www.reddit.com/r/LocalLLaMA/comments/1sn723c/people_still_dont_really_understand_what_agent
- [50pts] **MCP 跨厂商模型委派 server** → 主 app 内通过 MCP 把任务委派给别家模型，不离开主界面；model routing 模式印证我们的 hybrid 路由。https://www.reddit.com/r/ClaudeAI/comments/1v1tnmn/i_built_an_mcp_server_so_claude_code_can_delegate
- [50pts] **KodeAgent：SLM 函数调用加固** → 分阶段 loop 检测+nudging、执行前参数校验、结果截断、无 final_answer 时合成兜底；可直接借鉴到本地 Qwen 兜底层。https://www.reddit.com/r/LocalLLaMA/comments/1rkpbnv/built_a_functioncalling_agent_optimized_for_slms
- [45pts] **Claude Code/Codex CLI 宿主机资源问题** → 长会话内存增长 #22968、idle CPU 占用 #19393、进程累积 #11122；多 harness 并存时宿主资源是隐藏瓶颈。基于搜索摘要（r/LocalLLaMA 检索结果 3）

## 趋势判断

RLM 自修改 harness 崛起但 token 成本存疑；compaction 稳定性成共识痛点；上下文评测与 token 效率工程常态化。

---

### 最有价值 1 条

**Prime Agent 的社区反证实验**（deepseek-v4-flash 固定模型下 4.17M vs 2.06M tokens、同分 8/8）——它直接打脸"自修改 RLM harness 必然更好"的叙事，且测试模型正是我们生产环境所用的 deepseek-v4-flash：harness 差异可在相同模型上造成 2 倍 token 成本差。行动项：对 Prime Agent（open-source, TS/pi 栈，与我们的 sovereign-singularity TS 栈同构）跑一次同模型同任务成本对照，作为我们 harness 的 token 效率基准线。

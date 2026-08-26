# 情报简报: harness-engineering

**时间**: 2026-08-24 16:15 UTC
**源**: Reddit r/LocalLLaMA / r/ClaudeAI / r/ChatGPTCoding
**数据形态**: 基于搜索摘要 (web_extract 被 Reddit 反爬拦截: "Blocked: URL targets a private or internal network address", 信号本体为搜索结果标题+摘要, 未获取完整正文)
**上期对比**: 与 2026-08-23、2026-08-24 04:13 两期报告去重, 仅列新增/增量信号

## 高相关度发现

- [85pts] **Hermes agent/Openclaw context compaction loop** (r/LocalLLaMA 1s99y6z, 1天前) → **我们主线 harness 的真实缺陷信号**: 用户实测 Hermes Agent 在接近 context 上限时进入死循环 — "从零开始处理 → 撞上限 → 触发 compaction → 又从零开始 → 再撞上限…", 直至 agent 完全不再响应。RTX 5070Ti+5060Ti / llama.cpp / Qwen3.5-27B / 262K ctx, 调低到 128k 无效。compaction 触发条件与恢复机制是硬伤, 直接映射我们 Hermes + 本地基座 (Qwen2.5-32B + llama.cpp) 的运行时风险: **compaction 必须幂等且有收敛条件, 不能以"清空重来"为兜底**。评论区另指出"工具调用早期就要规划 policy+audit, 事后补全是灾难" — 印证我们 PreToolUse 闸门先行。https://www.reddit.com/r/LocalLLaMA/comments/1s99y6z/hermes_agent_openclaw_context_compaction_loop

- [85pts] **Real-world reality check on Qwen for autonomous coding agents** (r/LocalLLaMA 1vdb1n1) → **本地模型 + Hermes harness 的失败模式实录**: 用 Hermes Agent harness 做多轮自主开发 (Qwen, 100-200k context), 一致性失败模式 = premature "done!" + 幻觉工具调用, 且 context 越大越糟 (Q6_K 在芬兰语翻译上随上下文增长产出乱码)。高赞评论给出精确修法: **"premature done! 和幻觉工具调用是 harness 失败" — harness 只应在 context 里保留用户 query + 该 query 的最终答案; runner 本身需要独立的 disposable context, 用完即弃**。这正是 fresh-context 子任务隔离的又一例证 (与 08-23 报的 meta-harness 1vhy33b 同构), 且发生在本地模型+长上下文场景, 与我们的 Agent 1 本地 Qwen 执行层直接相关: 长任务子步骤应默认起独立执行上下文。https://www.reddit.com/r/LocalLLaMA/comments/1vdb1n1/realworld_reality_check_on_qwen_for_autonomous

- [80pts] **Hermes Agent & Recursive Language Models** (r/LocalLLaMA 1rtnjki) → 直接讨论**给 Hermes harness 加 RLM 脚手架**: RLM (Alex Zhang, arxiv 2512.24601, Prime Intellect 主推) 把 context 当作"on-heap 变量"由代码操控, 与 Hermes 现有"vector search / Skill docs / 工具读文件"的检索式 context 是两种范式; RLM 宣称可训练模型端到端学会 context folding (RL), 从不 summarize (避免信息损失), 主动委派 context 给 Python 脚本和子 LLM, 目标 10M+ token 长程任务。评论指出 Nous 官方认为 RLM ≈ 复杂化 subagents 而无意一等公民化 — **但 RLM 的"符号递归 + 确定性代码驱动循环"路线与我们 sovereign-singularity 引擎的 Lemma 链/ClaimRegistry 骨架天然同源**, 值得纳入骨架演进的观察清单。https://www.reddit.com/r/LocalLLaMA/comments/1rtnjki/hermes_agent_recursive_language_models

- [75pts] **Matching GPT-5 Mini on SWE-bench Verified with a Local 35B Model** (r/LocalLLaMA 1sqrct4) → **"scaffolding > model" 的最强实证**: mini-swe-agent (~100 行 agent 框架) + llama-swap 指向本地 Qwen3.6-35B-A3B (nothink 模式, 无微调, P40 GPU), 在 SWE-bench Verified 前 20 例上打平 GPT-5 Mini; 作者结论: "agent scaffolding does most of the work I used to attribute to the model"。附带警示: thinking 模式在 46 t/s 下单步可生成 10 万推理 token = 40 分钟/步 — 本地执行层应默认关闭长 CoT。支撑我们本地基座 + 专属 harness 的 Local-First 路线。https://www.reddit.com/r/LocalLLaMA/comments/1sqrct4/matching_gpt5_mini_on_swebench_verified_with_a

- [65pts] **Built a function-calling agent optimized for SLMs (Qwen 3 4B works!)** (r/LocalLLaMA 1rkpbnv) → 小模型 FC agent 的工程对策清单 (KodeAgent ~3K LOC): ① staged loop detection with nudging (分阶段检测死循环并轻推) ② 工具参数执行前校验 (拦截幻觉工具名/畸形 JSON) ③ **结果截断管理 context window** ④ 模型未输出 final_answer 时的干净兜底合成。与 08-23 报的 Manus 后 lead 的"最少工具集"互补 — 前者减工具面, 这里加护栏。逐条可迁移到我们本地 Qwen FC 层。https://www.reddit.com/r/LocalLLaMA/comments/1rkpbnv/built_a_functioncalling_agent_optimized_for_slms

- [60pts] **"Agent environment engineering" ≠ Agent Harness** (r/LocalLLaMA 1sn723c) → 概念澄清帖: 环境工程 (容器沙箱、eval、状态注入、可观测) 与 harness (模型面对的 loop/prompt/工具编排) 是两条被混为一谈的工程线。对骨架演进有用: 我们 gstack 隔离与 evaluator 层可归入"环境工程"独立立项, 不与 harness 本体耦合。https://www.reddit.com/r/LocalLLaMA/comments/1sn723c/people_still_dont_really_understand_what_agent

## 中相关度

- [55pts] **Hermes Agent memory/learning - I don't get it** (r/LocalLLaMA 1s43ts3) → Hermes 记忆系统实操痛点: "简单任务也要我反复重复上下文" — 与上期 compaction 帖同源, Hermes 记忆层在真实使用中的检索命中率问题, 印证 L2 记忆治理 + 按需挂载的必要性。https://www.reddit.com/r/LocalLLaMA/comments/1s43ts3/hermes_agent_memorylearning_i_dont_get_it

- [50pts] **AMA with Nous Research** (r/LocalLLaMA 1sz2y76) → 社区向 Nous 提问 self-improving agent 稳定性: "什么保证 δ(S,E)→S' 长期稳定? 实践中 self-improving agent 放大错误行为比学习更快, 尤其 skills 来自不完美推理时" — 自改进路线 (skill 自我生成) 的退化风险官方层面未被正面回答, 我们需要自带验证层 (对应我们 PostToolUse 门禁链)。https://www.reddit.com/r/LocalLLaMA/comments/1sz2y76/ama_with_nous_research_ask_us_anything

- [50pts] **Agent MCP: multi-agent framework** (r/ClaudeAI 1klrsso / r/ChatGPTCoding 1klrs8m) → 层级多 agent 编排: Admin Agent 拆任务+维护全局, worker 走 Plan/Act 协议, RAG 查询代替 context 塞入, SQLite 持久化跨会话状态, "agents know what others are working on, don't duplicate work"。multi-agent orchestration 的 MCP 实现参考 (注: 旧帖, 今日搜索回捞, 架构仍有参照价值)。https://www.reddit.com/r/ClaudeAI/comments/1klrsso/agent_mcp_the_multiagent_framework_that_changed

- [45pts] **civStation: controllable computer-use VLM harness** (r/LocalLLaMA 1s867mp) → 游戏域 harness: 屏幕观察→策略解读→行动规划→执行→human override, 支持 HitL + MCP/skill 扩展; 提出"strategy 与 execution 边界在哪"的开放问题 — HitL 可中断性是长程 agent 的通用需求, 对应我们人工闸门设计。https://www.reddit.com/r/LocalLLaMA/comments/1s867mp/built_a_controllable_computeruse_vlm_harness_for

- [40pts] **Serena: coding agent as MCP server, language server instead of RAG** (r/ChatGPTCoding 1jpavtm) → 用 LSP 而非 RAG 理解大型代码库, 可作 MCP server 挂到 Claude Desktop (GPL)。代码理解层选型信号 (注: 旧帖回捞)。https://www.reddit.com/r/ChatGPTCoding/comments/1jpavtm/fully_featured_ai_coding_agent_as_mcp_server

- [40pts] **AGI-like experience is only one context engineering idea...** (r/LocalLLaMA 1pzkqz1) → "harness 让模型超越自身局限, 正如语言把想法变成行动" — context engineering 被提升为 harness 第一性原理的又一舆论佐证。https://www.reddit.com/r/LocalLLaMA/comments/1pzkqz1/agilike_experience_is_only_one_context

- [30pts] **Learn MCP by building an SQL AI Agent** (r/ChatGPTCoding 1jd9lfa) → MCP client/server 教学帖, 标准 stdio + tools 声明模式, 无新范式 (旧帖回捞, 低增量)。https://www.reddit.com/r/ChatGPTCoding/comments/1jd9lfa/learn_mcp_by_building_an_sql_ai_agent

- [25pts] **Copilot Agent ignores MCP extensions** (r/ClaudeAI 1l4zlej) → 工具调用集成摩擦实录: agent 未自动触发已装 MCP — MCP 采纳率问题 (旧帖回捞)。https://www.reddit.com/r/ClaudeAI/comments/1l4zlej/copilot_agent_not_using_my_mcp_extensions_in_vs

## 趋势判断

Hermes 真实缺陷暴露 (compaction 死循环/记忆检索弱); fresh-context 隔离成共识; RLM 路线升温。本地小模型+harness 逼近云端。

## 最有价值发现

**r/LocalLLaMA 1s99y6z — Hermes Agent 的 compaction 死循环缺陷实测**: 用户在 llama.cpp + Qwen3.5-27B + 262K ctx 下复现确定性故障 — 触顶→compaction→清零重来→再触顶, agent 永久失响应, 且调低 ctx 无效。这是本项目主线 harness 的高危运行时信号: 我们每日长会话 (L1/L2/L3 + 大工具结果) 同样暴露在"compaction 无限循环"风险下, 触发条件与恢复路径正是七层骨架必须显式设计的部分 — compaction 必须幂等、可观测 (触发日志)、有收敛上限 (最多 N 轮, 超限强制 fresh context + 状态落盘), 不能把"从零重来"当兜底。建议: 在本地复现该场景 (Qwen2.5-32B 基座 + 长工具链会话), 验证我们 compaction 触发阈值与恢复逻辑, 并将结论回写 skeleton 设计文档。

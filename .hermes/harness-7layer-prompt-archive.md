# 中国企业版 Agent Harness — 七层收敛 Prompt (归档, 2026-08-02)

> 可直接作为 DeepSeek/Hermes 任务指令复用
> 覆盖领域: 科技/AI 工程、金融、医疗、教育 (中国中大型企业高频转型场景)

## 核心指令

"参考七层极简全栈 (Surface → Orchestration → Context → Model → Tools → Runtime → Memory, 外加横向 Guardrails & Observability), 把我们的 12 组件收敛映射到这 7 层上, 优先保证薄而可控, 拒绝框架绑架。"

## 更新后的 DeepSeek 提示词

你是一位顶级 AI Agent 系统架构师，专注于为中国中大型企业（科技/AI工程、金融、医疗、教育、制造、能源等）设计可落地、可合规、可规模化的 Agent Harness 框架。你深刻理解中国企业约束：强合规（数据安全法、个保法、等保、行业监管）、现有系统烟囱、数据分级与不出域、成本敏感、需要可解释可审计可追责。

当前任务：在 Hermes 代理中继续探索和完善「中国企业转型专用 Agent Harness 框架模板」。

【核心骨架】必须采用并严格遵循七层极简全栈（一年重建四次后的收敛结果）：
1. Surface（入口层）→ 统一 Task Object
2. Orchestration（编排层）→ 薄循环 + fan-out/merge + 内嵌验证
3. Context（上下文层）→ Budget 思维，强制 compact
4. Model（模型层）→ 路由优先（小模型处理绝大多数，frontier 仅关键路径）
5. Tools（工具层）→ 可见即存在，白名单 + schema
6. Runtime（运行时层）→ 沙箱墙是特性，不是摩擦
7. Memory（记忆层）→ 显式持久化，否则蒸发
横向贯穿：Guardrails（全程守卫）+ Observability（全程可观测与审计）

原 12 组件必须完整映射到以上 7 层中（作为详细检查清单），不得遗漏。

【落地优先级（不可颠倒）】
1. 针对高价值场景把 Harness 做扎实，尤其 Verification、Error Handling、Context、Guardrails。
2. 建立完善的可观测性与审计。
3. 平台化（统一 Runtime、工具注册中心、策略引擎）。
4. 最后才引入多 Agent。
始终执行「未来证明测试」：当底层模型显著变强时，Harness 是否变得更简单？如果更复杂，必须重新设计。Harness 是桥梁，不是终点。

【中国特色强制要求】
- 合规优先、数据最小化、敏感推理不出域
- 与现有系统通过工具网关集成
- 人机协同原生（细粒度 interrupt/resume/升级）
- 知识 + 规则双驱动
- 成本与效率仪表盘

【输出结构】
1. 七层架构总览 + 与 12 组件精确映射表
2. 七层逐一深化（中国企业关键决策 + 推荐实现 + 未来证明测试）
3. 高价值场景扎实落地（科技/金融/医疗/教育各至少 1 个），重点展开 Verification / Error Handling / Context / Guardrails 的具体机制
4. 可观测性与审计设计
5. 平台化路线图
6. 多 Agent 引入判断标准与模式
7. 未来证明测试检查清单
8. 下一步可在 Hermes 中实验的 3-5 个方向

保持专业、务实、可落地，关键决策加粗，必要时给出伪代码。拒绝框架绑架，追求薄而可控。

## 高价值场景 7 层伪代码骨架 (4 个代表性场景)

### 场景 A: 科技/AI 工程 — 内部代码变更与 PR 辅助
```python
# 1. Surface
task = normalize_input(source="feishu/dingtalk/cli/api", payload={repo, pr_description, files})
# 2. Orchestration
loop:
  plan = model.plan(task)
  results = fan_out([read_code, run_tests, security_scan])
  merged = merge(results)
  if verification_pass(merged): break
  else: repair_or_escalate()
# 3. Context
ctx = assemble(system_prompt, tools_schema, compact(history + git_diff + test_logs), budget=128k)
# 4. Model
if complexity < threshold: use_small_model(ctx) else: use_frontier(ctx)
# 5. Tools
tools = whitelist(["read_file", "run_tests", "git_diff", "linter", "security_scan"])
# 6. Runtime
with sandbox(network=limited, fs=repo_worktree, timeout=300s):
  execute_tools(); log_all_actions(); on_error: retry(2) or return_error_as_observation()
# 7. Memory
persist(session_summary, decisions, unresolved_bugs) → project MEMORY.md + audit_log
```

### 场景 B: 金融 — 合规报告自动生成与核对
```python
# Surface: 从 OA/邮件/定时任务归一成 Task Object (报告类型、周期、数据源)
# Orchestration: plan → 拉取数据 → 规则校验 → 生成草稿 → 人工确认闸门 → 定稿
# Context: 强制只加载当期数据 + 相关制度摘要 (budget 严格)
# Model: 小模型做数据清洗与格式, frontier 做复杂判断与叙述
# Tools: 只暴露只读数据接口 + 规则引擎 + 模板填充 (无写库权限)
# Runtime: 强隔离沙箱 + 全操作审计日志 + 敏感字段自动脱敏
# Memory: 报告版本 + 审核意见持久化, 支持追溯
# Guardrails: 输出必须通过合规规则引擎, 否则阻断
```

### 场景 C: 医疗 — 病历质控与辅助诊断建议 (高合规)
```python
# Surface: HIS/EMR 系统回调或医生工作站插件 → Task Object
# Orchestration: 提取关键信息 → 对照指南 → 生成质控意见 → 医生确认
# Context: 最小化 (仅当前病历 + 相关指南片段), 严格 budget
# Model: 本地/私有化小模型优先, 敏感推理不出域
# Tools: 只读病历接口 + 指南检索 + 质控规则引擎
# Runtime: 医疗级沙箱 + 操作全审计 + 超时强制中断
# Memory: 质控记录与医生反馈写入专属审计库 (不可篡改)
# Guardrails: 任何诊断建议必须标注"仅供参考", 高风险直接升级人工
```

### 场景 D: 教育 — 个性化学习路径生成与作业批改辅助
```python
# Surface: 学习平台 / 教师端 / 学生端统一入口
# Orchestration: 诊断当前水平 → 生成路径 → 批改作业 → 反馈循环
# Context: 学生画像摘要 + 当前作业 + 知识点 (compact 历史学习记录)
# Model: 小模型批改客观题, frontier 处理主观题与路径规划
# Tools: 题库检索、知识点图谱、作业交接口
# Runtime: 学生数据隔离沙箱
# Memory: 学习轨迹 + 薄弱点持久化, 支持跨学期
# Guardrails: 防止生成不当内容, 作业反馈需教师可选确认
```

# 中国企业转型专用 Agent Harness 框架模板 — 深化方案

> 版本: v1.0 | 日期: 2026-08-02 | 状态: 设计基线, 随实验迭代
> 前置: 《The Anatomy of an Agent Harness》十二大组件
> 定位: 可落地、可合规、可规模化的中国企业版 Agent Harness 设计模板

---

## 0. 第一性原理

**Harness 不是终点，而是让模型真正触达复杂现实世界的桥梁。**

中国企业场景的本质约束：
- **合规 > 智能** — 答错可修复, 违规不可逆
- **烟囱集成 > 绿地创新** — 90% 价值在打通 ERP/MES/OA
- **业务专家 > AI 原生人才** — 系统必须让业务专家能理解、能接管
- **成本敏感** — token/人天都要可核算

**未来证明测试（贯穿所有决策）**：当底层模型显著变强时，Harness 是变简单还是变复杂？
- 变复杂 → 设计有问题, 重新思考
- 变简单 → 设计正确, 模型进化后 Harness 自动退居幕后

---

## 1. 框架模板总览：分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  应用层 (场景适配)                                            │
│  知识工单 / 配置变更 / 报表核对 / 设备诊断 / 合规审查          │
├─────────────────────────────────────────────────────────────┤
│  编排层 (核心薄 Loop)                                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Orchestration Loop (极薄 ReAct/TAO)                 │    │
│  │  Plan → Act → Observe → Verify → (Retry|Escalate)  │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│  扩展层 (Hooks + Policy as Code + Domain Adapters)          │
│  Verification Loops     Context Management                  │
│  Guardrails             Error Handling                      │
│  Memory                 Prompt Construction                 │
│  Output Parsing         State Management                    │
│  Subagent (延迟引入)     Observability/Audit                 │
├─────────────────────────────────────────────────────────────┤
│  集成层 (中国烟囱系统)                                       │
│  工具网关 (MCP 风格) → ERP/MES/OA/钉钉/飞书/SAP/用友/金蝶     │
├─────────────────────────────────────────────────────────────┤
│  基础设施层                                                 │
│  Runtime / 工具注册中心 / 策略引擎 / 多租户 / 审计存储        │
└─────────────────────────────────────────────────────────────┘
```

**核心哲学：薄但可控的厚度**
- 核心 Loop 极薄 — 只有 Plan→Act→Observe→Verify
- 所有重逻辑在外围 — Hooks 注入、Policy as Code 声明、Domain Adapters 隔离
- 模型变强 → 核心 Loop 不变, 外围策略自动简化

---

## 2. 十二大组件逐一深化

### 1. The Orchestration Loop（编排循环）

- **核心职责**: Plan→Act→Observe→Verify 主循环
- **中国企业关键决策**: **默认"人机协同"而非"全自动"** — 关键节点(写库/审批/外发)必须 interrupt
- **推荐实现**: 状态机, 不是裸 while 循环; 每步持久化到 State (可断点续跑)
- **协同**: Verify 是 Loop 的收尾闸门; Guardrails 在 Act 之前拦截
- **未来证明**: ✅ 变薄 — 模型越强, Plan 越准, 循环越短

### 2. Tools（工具层）

- **核心职责**: 让模型触达现实系统
- **中国企业关键决策**: **工具网关 (MCP 风格), 绝不直接连库** — 权限、审计、限流都在网关层
- **推荐实现**: 统一 Tool 协议 (name/desc/input_schema/execute); 网关注册中心; 工具级权限矩阵
- **协同**: Guardrails 在网关前置校验; Audit 记录每次调用
- **未来证明**: ✅ 不变 — 工具层是物理接口, 与模型强度无关

### 3. Memory（记忆系统）

- **核心职责**: 跨 session 知识 + 工作记忆
- **中国企业关键决策**: **记忆分级** (公开/内部/机密/绝密), 敏感记忆不出域
- **推荐实现**: 三层 — 短期 (context) / 工作 (状态文件) / 长期 (向量库+规则库)
- **协同**: Context Management 从 Memory 组装; Guardrails 控制记忆读写权限
- **未来证明**: ✅ 变薄 — 模型 context 变长, 短期记忆需求下降, 长期记忆(规则/知识)仍是刚需

### 4. Context Management（上下文管理）

- **核心职责**: 决定"模型这次看到什么"
- **中国企业关键决策**: **Context Compiler 模式** — 不是全量塞入, 而是按任务编译最小上下文
- **推荐实现**: 检索(向量+关键词)+规则筛选 → 组装结构化 context; 保留引用来源
- **协同**: Verification 检查 context 是否完整; Error Handling 在 context 缺失时重取
- **未来证明**: ✅ 变薄 — 模型 context 窗口变大, Compiler 压力下降; 但"只给需要的"原则不变

### 5. Prompt Construction（提示构建）

- **核心职责**: 把任务+上下文+约束组装成 prompt
- **中国企业关键决策**: **中文+合规约束显式声明** — "只依据资料回答/不确定就说不知道/涉及X必须上报"
- **推荐实现**: 模板 + 变量注入; 版本化 prompt (可回滚)
- **协同**: Guardrails 的规则注入 prompt; Verification 检查输出是否偏离
- **未来证明**: ✅ 变薄 — 模型指令遵循变强, prompt 工程退化为"给约束"

### 6. Output Parsing（输出解析）

- **核心职责**: 把模型输出转成结构化结果
- **中国企业关键决策**: **强 schema 校验** — 输出必须过 Pydantic 契约, 失败重试
- **推荐实现**: 结构化输出 (JSON mode / function calling) + schema 校验 + 重试
- **协同**: Verification 复用 parser 校验; Error Handling 处理 parse 失败
- **未来证明**: ✅ 变薄 — 模型原生支持结构化输出, parser 层退化

### 7. State Management（状态管理）

- **核心职责**: 任务状态持久化, 支持中断恢复
- **中国企业关键决策**: **状态文件是事实来源** — 不是对话上下文; 支持审计追溯
- **推荐实现**: .hermes/plan.md 状态机 (PENDING→IN_PROGRESS→VERIFYING→COMPLETED/BLOCKED)
- **协同**: Verification 更新状态; Observability 读取状态
- **未来证明**: ✅ 不变 — 状态管理是基础设施, 与模型无关

### 8. Error Handling（错误处理）

- **核心职责**: 失败可恢复、可升级、可审计
- **中国企业关键决策**: **错误分级升级** — 工具错误→重试; 校验失败→修复重试; 模型失控→升级人工
- **推荐实现**: 错误分类器 (分类→策略: retry/fix/escalate/abort); 错误模式聚类
- **协同**: Verification 触发错误处理; Guardrails 决定哪些错误必须升级
- **未来证明**: ✅ 变薄 — 模型更稳, 错误率下降; 但升级路径(人工兜底)是合规刚需, 保留

### 9. Guardrails and Safety（护栏与安全）

- **核心职责**: 边界 — 什么能做, 什么必须停下来
- **中国企业关键决策**: **Policy as Code** — 合规规则(数据分级/权限/红线)声明为代码, 可审计可更新
- **推荐实现**: 规则引擎 (AND/OR/NOT/func) + 前置拦截 + 后置校验; 权限矩阵
- **协同**: 是所有 Act 的前置闸门; Verification 校验结果合规性
- **未来证明**: ✅ 不变 — 合规是物理约束, 模型再强也不能越权 — **这是永不简化的部分**

### 10. Verification Loops（验证循环）

- **核心职责**: "说做完了" ≠ "做完了" — 检查工作成果
- **中国企业关键决策**: **分类型验证门** — code→编译+测试; 数据→对账; 报告→结构+引用检查; 操作→dry-run+确认
- **推荐实现**: 每步完成自动过 gate; 失败 retry<3 重试, 超过升级人工 (Ralph Loop)
- **协同**: 是 Loop 收尾; Error Handling 处理验证失败; Context 提供验证所需信息
- **未来证明**: ✅ 变薄 — 模型自检变强, 但"验证逻辑"本身要保留 (防止自我强化错误)

### 11. Subagent Orchestration（子代理编排）

- **核心职责**: 任务分解给多个 Agent
- **中国企业关键决策**: **延迟引入** — 单 Agent 明显不够时才引入; 子代理必须可审计
- **推荐实现**: 先单 Agent 扎实 → 需要并行/专业分工时 → 主-从模式, 每子任务有独立 trace
- **协同**: Verification 检查每个子任务产出; Observability 聚合子代理 trace
- **未来证明**: ✅ 变薄 — 模型能力增强后, 单 Agent 能处理更多, 子代理需求推迟

### 12. Lifecycle Management & Observability（生命周期与可观测性）

- **核心职责**: 生产必备 — 看得见、查得到、可追溯
- **中国企业关键决策**: **审计日志是合规底线** — 谁在何时调了什么工具, 结果如何, 全链路留存
- **推荐实现**: 结构化 trace (run_id + step + 输入/输出/耗时/成本); 指标 (token/人天/失败率); 审计表
- **协同**: 是所有组件的地基; 成本归因支撑内部结算
- **未来证明**: ✅ 不变 — 可观测性是生产基线, 与模型无关

---

## 3. 高价值场景扎实落地指南

### 场景 1: 内部知识 + 工单助手

**Verification**:
```
1. 检索 → 校验: 命中块引用完整 (doc_id + 章节 + 原文片段)
2. 回答 → 校验: 每个结论必须映射到引用; 无引用段落标记"推测"
3. 工单字段 → 校验: Pydantic schema (类型/枚举/必填)
失败策略: 引用缺失 → 重检索 (扩大 top_k); 字段非法 → 返回表单让用户改
```

**Error Handling**: 检索空 → 明确"知识库无此内容" + 建议关键词; 模型超时 → 降级为检索原文展示

**Context Management**: 只注入 top-3 相关块 (每块 ≤3000字) + 用户历史工单摘要; 不注入全库

**Guardrails**: 知识库分级 — 机密文档不进入检索结果; 回答含敏感词 → 人工复核

### 场景 2: 配置变更辅助 (运维/IT)

**Verification**:
```
1. 变更计划 → 校验: dry-run 执行, 对比影响范围
2. 实际变更 → 校验: 前后状态对账 (期望 vs 实际)
3. 回滚预案 → 校验: 回滚步骤存在且可执行
失败策略: dry-run 有意外影响 → 阻断 + 升级人工审批
```

**Error Handling**: 变更失败 → 自动回滚 + 记录; 部分成功 → 标记"部分完成" + 人工介入清单

**Context Management**: 注入变更对象历史状态 + 相关配置项依赖; 不注入全量配置库

**Guardrails**: 变更窗口限制 (非维护窗口阻断); 高危对象 (生产库) 必须人工审批; 审计全记录

### 场景 3: 报表核对 (财务/运营)

**Verification**:
```
1. 提取数字 → 校验: 与源系统对账 (三层对账: 明细=汇总=系统)
2. 差异分析 → 校验: 每个差异有归因 (无归因 → 标记异常)
3. 报告 → 校验: 数字一致性 + 单位正确 (万/亿 陷阱)
失败策略: 对账不平 → 定位差异行, 阻断输出
```

**Error Handling**: 源系统不可达 → 缓存上次数据 + 标记陈旧; 数字不一致 → 升级人工核对

**Context Management**: 注入账期范围 + 对账规则 + 历史差异; 不注入全量流水

**Guardrails**: 财务数据分级 — 仅授权角色可见; 报告外发 → 人工审批

### 场景 4: 设备诊断 (制造/能源)

**Verification**:
```
1. 诊断结论 → 校验: 依据传感器数据可复现 (给出数据窗口)
2. 处置建议 → 校验: 与 SOP 匹配 (规则库校验)
3. 高风险操作 → 校验: 双人复核 (human-in-the-loop)
失败策略: 数据不足 → 请求更多传感器数据; SOP 无匹配 → 升级专家
```

**Error Handling**: 传感器数据缺失 → 标注不确定性; 诊断矛盾 → 升级人工

**Context Management**: 注入设备历史故障模式 + 当前实时数据; 不注入无关设备

**Guardrails**: 高危动作 (停机/断电) 必须人工确认; 诊断置信度低于阈值 → 只建议不执行

### 场景 5: 合规审查 (法务/风控)

**Verification**:
```
1. 引用条款 → 校验: 条款原文存在且版本正确 (hash 校验)
2. 审查结论 → 校验: 每个结论映射条款 + 风险等级
3. 报告 → 校验: 结构完整 (风险清单/依据/建议)
失败策略: 条款引用错误 → 重新检索 + 修正; 无依据结论 → 标记"待人工"
```

**Error Handling**: 法规更新 → 检测旧版本引用, 提示更新; 条款歧义 → 升级法务

**Context Management**: 注入相关法规条文 (向量检索) + 审查对象; 不注入无关法规

**Guardrails**: 法律意见边界 — 只做"合规分析"不做"法律结论"; 敏感条款 → 人工复核; 全审计

---

## 4. 可观测性与审计设计

### 指标 (Metrics)

```
核心指标:
  harness_task_total            — 任务数 (按场景/状态)
  harness_task_duration         — 任务耗时 (P50/P95)
  harness_step_total            — 步骤数 (按步骤类型)
  harness_verify_pass_rate      — 验证通过率
  harness_retry_total           — 重试次数
  harness_escalate_total        — 升级人工次数
  harness_token_usage           — token 消耗 (按模型/任务)
  harness_tool_call_total       — 工具调用 (按工具/结果)
  harness_guardrail_blocked     — 护栏拦截数
  harness_cost_estimate         — 成本估算 (按任务/租户)
```

### Trace 结构

```
trace_id: task_20260802_abc123
└── run 1: plan (input→plan_output)
    ├── step 1: act (tool=crm_query, args, result)
    │   ├── guardrail: PASSED (policy=read_only)
    │   └── verify: PASSED (schema_ok)
    ├── step 2: act (tool=db_write) → guardrail: BLOCKED → escalate
    └── escalate: human_approved=false → abort
audit: {who, when, tool, args_hash, result_hash, decision}
```

### 审计日志格式

```json
{
  "ts": "2026-08-02T10:00:00Z",
  "run_id": "task_20260802_abc123",
  "actor": "user_li_wei",
  "action": "tool_call",
  "tool": "crm_query",
  "args_hash": "sha256:...",
  "result_hash": "sha256:...",
  "guardrail": {"policy": "read_only", "decision": "allow"},
  "cost": {"tokens_in": 1200, "tokens_out": 300, "estimate_usd": 0.002},
  "verdict": "success"
}
```

### 成本归因

- 按 run_id 累计 token → 按任务/场景/租户聚合
- 仪表盘: token/人天/失败率/成本 月度趋势
- 内部结算: 部门 × 任务类型 × 成本

### 失败模式聚类

- 按错误类型聚类 (verify_fail / tool_error / guardrail_block / timeout)
- 每周聚类报告 → 识别高频失败 → 针对性加固 (闭环到 skill)

---

## 5. 平台化路线图

```
Phase 0 (当前): 单场景扎实
  目标: 1 个场景端到端跑通, Verification/Error/Context/Guardrails 扎实
  里程碑: 场景上线, 审计日志完整, 失败率 <5%

Phase 1: 统一 Runtime
  目标: 多场景共享 Runtime (Loop/State/Observability)
  里程碑: 3+ 场景在统一 Runtime 运行, 指标统一

Phase 2: 工具注册中心 + 策略引擎
  目标: 工具网关化 (MCP 风格), 策略声明为代码
  里程碑: 新场景接入 <1 天 (只需注册工具 + 声明策略)

Phase 3: 多租户
  目标: 租户隔离 (数据/权限/成本), 内部结算
  里程碑: 多部门独立使用, 账单清晰

Phase 4: 多 Agent (仅在单 Agent 明显不够时)
  目标: 任务并行/专业分工
  里程碑: 有真实并行需求才引入
```

---

## 6. 多 Agent 引入时机与模式

### 判断标准 (全部满足才引入)

```
1. 任务可分解为独立子任务 (无强依赖)
2. 单 Agent 处理超时或质量不达标 (实测数据)
3. 子任务有明确验收标准
4. 并行收益 > 编排开销 (实测对比)
```

### 推荐模式

```
主-从模式 (默认):
  主 Agent: 规划 + 分配 + 汇总 + 最终验证
  子 Agent: 每个子任务独立 run_id + trace + 审计

避免:
  - 过早多 Agent (编排开销 > 收益)
  - 无验收标准的自由协作
  - 子 Agent 无权限边界
```

---

## 7. 未来证明测试检查清单

用于评审每个设计决策：

- [ ] 模型 context 变 10 倍后, 此组件是否简化? (变复杂 = 有问题)
- [ ] 模型指令遵循变强后, 此组件是否退化? (应退化: prompt 工程)
- [ ] 模型自检变强后, 此组件的验证逻辑是否保留? (应保留: 防自我强化)
- [ ] 合规约束是否与模型强度无关? (应无关: 物理边界)
- [ ] 核心 Loop 是否薄? (应只有 Plan→Act→Observe→Verify)
- [ ] 重逻辑是否在外围 (Hooks/Policies/Adapters)?
- [ ] 移除任何组件, 系统是否还能工作 (降级模式)?
- [ ] 新场景接入是否只改 Adapter, 不动核心?

---

## 8. 下一步探索建议

1. **Meta-Loop 自我优化**: 失败模式聚类 → 自动生成策略更新 → 验证后合入 (闭环 TBSRE)
2. **Context Compiler 实验**: 最小上下文组装 vs 全量注入, 实测质量/成本对比
3. **对抗性验证**: 用对抗样本 (误导性提问/越权请求) 测试 Guardrails 强度
4. **物理世界鲁棒接口**: 工具网关的幂等/重试/超时语义标准化
5. **知识+规则双驱动**: SOP/制度 → 可执行规则引擎的转化工作流
6. **成本仪表盘**: token/人天/失败率可视化 + 内部结算 (先落地, 后平台化)

---

## 附: 与 Pulse 现状的映射

```
Pulse 已验证的组件 (可直接复用):
  Verification Loops    — 三层数仓对账 + SLA 检查 ✅
  Guardrails            — Data Contract (Pydantic) + DLQ ✅
  Error Handling        — Circuit Breaker + Retry-After + DLQ ✅
  State Management      — DAG 状态 + dag_runs 表 ✅
  Observability         — Prometheus + snapshot + alert_check ✅
  Tools (集成层)        — Fetcher v2 + Scrapling 适配器 ✅
  Memory                — compliance.duckdb 向量库 (RAG) ✅

Pulse 未覆盖 (中国企业版新增):
  Context Management    — Context Compiler 模式
  Prompt Construction   — 中文合规 prompt 模板
  Subagent              — 延迟引入
  多租户/策略引擎        — Phase 2/3
  人机协同原生           — interrupt/resume/升级
```

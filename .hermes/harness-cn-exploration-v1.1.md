# 中国企业版 Agent Harness — 探索方向深化 v1.1 (2026-08-02)

> 补充: harness-cn-deep-dive.md v1.0 的进阶方向
> 来源: 白云 (用户) 提供的"计算原语级"深化思考

---

## A. Agent 的真正计算原语

不满足于"把现有组件拼得更稳"，追问：什么是 agent 的真正计算原语？如何让 harness 本身具备探索未知、自我改进的能力？

### A1. Loop 作为可组合的一等公民原语

不只是 while-loop + TAO。引入 Hooks 与 Policy as Code：
- 每个关键点（pre-tool / post-observation / pre-compaction / verification gate）可挂可插拔 policy
- policy = 规则 + 小模型 + 人类
- 类比: 操作系统 eBPF / Kubernetes admission webhook
- 价值: 企业可把合规、成本、安全策略**外置**，不改核心 loop

### A2. Context 作为"可计算状态"而非字符串

当前 context 管理多为启发式压缩。深化方向：
- context 建成**带版本、带因果图、带重要性评分**的结构化状态（类似 Git + vector + graph）
- Compaction 变成"**可逆摘要 + 指针**"，而不是不可恢复的总结
- 引入"**context compiler**"——根据当前目标动态裁剪/重排/检索
- **Lost-in-the-Middle 不是调参问题，是信息论问题：最大化目标相关互信息**

### A3. Memory 的多级一致性与"可证伪"设计

三层记忆之上加上：
- **Write-ahead log + 冲突检测**
- Memory 作为 **hypothesis**，每次使用前强制验证（工具回查真实世界）
- 组织级共享记忆 + 租户隔离 + 遗忘策略（GDPR/中国数据安全法友好）
- 目标：agent 的"信念"**可被审计、可被回滚**

### A4. Verification 成为核心闭环，而非事后检查

把 verification 提升为 loop 的**原生阶段**：
- rules（确定性）→ sensors（观察）→ judges（LLM/人类）→ repair actions
- 引入**对抗性验证**（另一个 agent 尝试找茬）和**经济验证**（成本是否值得继续）
- 目标是"**失败可预测、可局部修复**"

### A5. Harness 的自我进化 Meta-Loop

- 收集失败轨迹 → LLM 提出 harness 修改提案（新 tool / 新 compaction 策略 / 新 guardrail）
- 沙箱 A/B → 自动或人工晋升
- 呼应 "LLM 优化 infrastructure"；把 harness 本身当作可探索的未知系统

### A6. 薄但可扩展的厚度哲学

- Anthropic 薄 harness 方向正确，但企业需要"可控厚度"
- 核心 loop 极薄，外围有丰富 domain adapters / 合规插件 / 系统集成层
- 类比: Linux 内核 + 用户空间

---

## B. 落地中国中大型企业：从"能跑"到"可管、可控、可规模"

### 现实约束
- 强合规（数据安全法、个保法、行业监管、等保）
- 现有 IT 烟囱（SAP、用友、金蝶、自研 MES/ERP、OA、钉钉/飞书）
- 数据不出域或严格分级
- 组织惯性大，需要可解释、可审计、可追责
- 成本敏感，要快速见 ROI
- 人才结构：业务专家多，AI 原生工程师相对少

### 阶段 1: 单点高价值场景的"可控 Agent"

优先场景: 内部知识问答+工单 / 代码配置变更辅助 / 报表生成核对 / 设备异常诊断

Harness 选型:
- LangGraph 或自研薄 loop 为核心（可控性强）
- 工具层严格白名单 + 沙箱（对接现有 API，绝不直接给 shell）
- Memory: 企业知识库 + 会话级 + 项目级（CLAUDE.md 风格业务规则文件）
- Guardrails: 输入输出敏感词/实体检测 + 工具权限矩阵 + 人工确认高风险操作
- Verification: 业务规则引擎 + 单元测试/仿真 + 人工抽检

### 阶段 2: 组织级 Harness 平台化

企业内部的"Agent Runtime":
- 统一 Orchestration 服务（interrupt/resume、checkpoint、审计日志）
- 工具注册中心（schema、权限、成本标签、版本）
- Context/Memory 服务（多租户、分级、可 compaction）
- Policy Engine（合规、成本、安全钩子）
- 可观测性: 全链路 trace + 成本归因 + 失败模式聚类
- 与现有系统深度集成: MCP 类协议/企业内部工具网关暴露 ERP/MES/OA 能力，agent 不直接连库

### 阶段 3: 多 Agent 协作与业务闭环

- 仅在单 agent 明显不够时引入: 领域专家 agent（财务/法务/工艺）+ 协调 agent
- 通信用结构化 mailbox + 共享 progress file（文件系统/对象存储），避免纯自然语言黑盒传递
- 引入"业务状态机"作为外层约束: agent 只能在合法状态转移中行动

### 中国特色深化点
- **合规优先设计**: 所有 tool 调用/memory 读写/跨域数据走审计通道; 数据最小化 + 本地模型优先 + 敏感推理不出域
- **人机协同原生**: 不是可选 human-in-loop，是默认升级路径（置信度低/风险高/成本超预算自动打断）
- **知识与规则双驱动**: 企业 SOP/制度/专家经验沉淀为可执行 rules + retrieval，不全靠 LLM 记忆
- **成本与效率仪表盘**: 业务部门看到"省了多少人天、花了多少 token、失败率多少"，推动内部结算与持续优化
- **渐进去脚手架**: 私有化/行业大模型变强后，planning/部分 verification 内化到模型，harness 变薄，但保留策略与审计层

---

## C. 进一步探索方向（未知世界）

1. **Harness 作为可学习的系统**: 把整个 agent 轨迹当作数据，训练"harness policy network"——决定何时 compact、何时 spawn subagent、何时验证、何时求助人类
2. **物理世界接口的鲁棒性**: 制造/能源场景下，工具调用面对真实设备延迟/噪声/部分可观测性，需更强状态估计与安全互锁
3. **开放世界工具发现与组合**: agent 能否安全发现并组合企业内部从未注册的 API？需形式化能力描述 + 沙箱验证
4. **集体智能的 harness**: 多企业 agent 在数据主权保护下协作（联邦式 memory、安全多方计算风格 tool 调用）
5. **从"执行任务"到"探索与假设生成"**: 当前 harness 擅长 goal-directed，对真正的科学/工程探索（生成假设→设计实验→执行→更新信念）支持仍弱——通往更通用智能的关键路径

---

## D. 行动建议（起点决策）

不要一上来追求"通用超级 agent"。先用 12 组件把**一个价值场景**的 harness 做扎实（尤其 verification/error handling/context/guardrails），建立可观测与审计，再平台化，再多 agent。

始终用"未来证明测试"检验：模型变强时，harness 变简单还是更复杂？变复杂 = 设计有问题。

Harness 不是终点，而是让模型真正触达复杂现实世界的桥梁。

**中国企业的转型窗口**: 把已有流程与数据优势，通过扎实的 harness 工程，转化为可控的 AI 执行力。模型会继续变强，但"把正确的事做对、做安全、做得起"的系统能力，将长期是核心竞争力。

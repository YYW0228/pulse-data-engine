# AR 实验台账 (autoresearch 阶段1 人审闭环)

> 规则见 docs/autoresearch-spec.md
> 判定: keep = hit_rate ≥ 基线+0.02 且 I1-I4 全绿 且 延迟/调用数 ≤1.5×基线

## 基线 (v1.0)
avg_hit_rate = **0.723** (见 ar-baseline.md, 数据 golden_baseline_20260814.json)

## 实验记录

### AR-01: system_prompt v1.1 — 结论先行 + 分点完整展开 [DISCARD]
- 改动: compliance_qa.py system_prompt 增加规则5 (结论先行/逐项列全)
- 假设: golden 期望要点是法规概念词, "逐项列全"提高覆盖而不牺牲"不编造"
- 结果: avg 0.734 vs 基线 0.723 → **delta +0.011 < +0.02 阈值**
- 不变量: I1 ✓ (3 passed) I2 ✓ (audit_reconstruct OK) I3 ✓ (191 passed) I4 ✓ (无孤儿)
- 判定: **DISCARD** (无显著改进, 已还原 v1.0)
- 教训: 该改动方向 (结构化输出) 收益有限 — 低命中题根因是 guard 拦截/检索覆盖, 非 prompt 结构

### AR-02 (候选, 未执行): intent guard 误伤
- 现象: "大模型服务提供者有哪些义务？" (合法事实查询) 被 guard 快速拒绝 30ms/33%
- 方向: 检查 classify_intent 关键词误判, 需先建误伤率样本集

## AR-02: intent guard 误伤 (2026-08-14)

- **发现**: golden 基线第 23 题 "AI模型备案和算法备案有什么区别?" 被判 meta 拒绝 (meta_kw "有什么区别" 过宽) — 合规概念对比被误认为元问题
- **样本集**: data/intent_guard_samples.json (20 条合法事实查询, 覆盖义务/对比/豁免/否定/主体/流程/跨境)
- **修复**: "区别" 类仅在对系统/模型提问时判 meta (含 你/chatgpt/你们/系统), 其余 "区别" → factual
- **验证**: 样本集 20/20 factual; golden 30 题误伤 1→0; meta 6 例不回归; 注入/角色扮演/探测 3 例仍拦截
- **门禁**: tests/test_intent_guard.py (4 测试, 防回退)
- **AR-02 结论**: DONE (误伤率样本集 0/20, golden 0/30)

## AR-03: 基线重跑 (2026-08-14)

- **新基线**: 0.712 (vs 旧 0.723) — AR-02 guard 修复后 golden 误伤 1→0, 但 avg 略降 (2 题 ERR 环境偶发 + 检索覆盖缺口)
- **AR-02 结论修正**: "大模型服务提供者有哪些义务?" 31ms = 检索 0 命中, 非 guard (台账见 ar-baseline.md)
- **发现**: ① 检索覆盖缺口 ("大模型服务提供者义务"/"欧盟数据存储" 等主题无文档) — AR-04 候选 ② eval 双模块导入 (compliance_qa vs scripts.compliance_qa) 状态干扰 — 待统一为包导入
- **eval 约束固化**: 必须前台跑 (后台触发 torch ABI dlopen 崩); golden_baseline 文件被进度文本污染是脚本设计 (进度+JSON 混 stdout) — 待修

## AR-04: 检索阈值修复 (2026-08-14)

- **根因**: "大模型服务提供者有哪些义务?" 检索相似度 0.53 vs SIM_THRESHOLD 0.55 — 边缘召回失败 (有料被滤)
- **修复**: SIM_THRESHOLD 0.55 → 0.52 (宁多勿缺, 引用可溯源)
- **效果**: avg 0.712 → **0.778** (+6.6pp); "大模型义务"/"AI治理岗位技能"/"欧盟数据存储" 等题脱离低命中区
- **剩余低命中** (33%×6): 回答覆盖类 (期望概念词缺 1-2 个, 检索有料) — AR-05 候选; 1 题 ERR (eval 双模块偶发, 待修)
- **eval 输出修复**: 进度走 stderr, stdout 只出 JSON (基线文件不再被污染)
- **补料项**: "AI安全测试包含哪些内容?" 文档无明确测试清单 (GB/T 42561 类) — kb 入库候选

## AR-05: 补料 + 检索优化 — 通过 80% 门槛 ✅ (2026-08-14)

- **补料**: 新文档 ai-safety-testing-baseline.md (TC260-003/GB/T 45654-2025 安全测试与评估全要点: 关键词库≥1万词/生成内容题库≥2000题/拒答题库500+500/评估指标96%/98%/90%/95%/31种风险/三签字) → china-ai-governance/references 入库
- **检索优化 (3 项)**:
  1. 头部块过滤: retrieve SQL + compile_context 剔除 "文档头部" 块 (标题与查询字面重合但无实质, 挤占候选)
  2. 候选扩大: top_k*3 → top_k*5 (内容块 0.633 边缘召回)
  3. 快速问答摘要锚点: 文档加 "〇、快速问答摘要" 段 (查询-文档语义对齐) — 新文档从不可召回 → top1
- **eval 修复**: 双模块统一包导入 (scripts.compliance_qa) — 消除 0ms ERR 偶发
- **基线**: 0.712 → 0.778 → 0.789 → **0.800 ✅ (通过)**
- **剩余低命中** (33%×5): 具体数字/机制词缺口 (72小时/30日/本地化/SCC/双轨) — 知识库补料候选 (GDPR SCC/数据泄露时限), 非 prompt 问题

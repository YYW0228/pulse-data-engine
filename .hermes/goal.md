# Goal Contract — Pulse Data Engine 直播准备 + Harness 加固 + 吞噬进化

## Goal
完成 Pulse Data Engine 的直播就绪状态, 同时补上 Hermes 的 Goal Contract 基础设施, 并通过吞噬外部 harness 持续进化架构。

## Success Criteria
- [ ] `.hermes/goal.md` 协议定义完成, 可作为模板复用
- [ ] 自动校验: 每次回答前检查是否有未完成 goal
- [ ] 如有新 Telegram 消息, 主动拉取并处理
- [ ] Dashboard 直播功能全开 (自动刷新/全屏/时间戳)
- [ ] 市场洞察脚本可生成报告
- [x] 吞噬工具链完整 (评分卡/模式库/雷达/脚手架/CI)
- [x] Rule of Three 达成 (3 次实战: 5仓库/boxsh/mini-claude-code)
- [x] T1-T5 吞噬模式全部落地 (缓存/证据/循环/压缩/记忆)

## Steps
- [x] Step 1: 定义 Goal Contract 结构 → type:document | verify:passed
- [x] Step 2: 实现 Goal 校验逻辑 (检查文件状态) → type:code | verify:passed
- [x] Step 3: 绑定到 session 启动流程 → type:code | verify:passed
- [x] Step 4: 验证 Telegram inbox → type:generic | verify:passed
- [x] Step 5: 检查 Dashboard/Metrics 状态 → type:generic | verify:passed

## State
goal_contract: completed
telegram_bridge: completed
dashboard_live_ready: completed
market_insight: pending

## Pending (Telegram 2026-08-01, 更新 2026-08-12)
- [ ] 分析 x.com/pluvio9yte/2082386081794961733 — 可借鉴技能 (抓取受限, 需白云手动分享内容; browser 需 Chrome 远程调试授权)
- [x] 吞噬 LLMs-from-scratch (rasbt) → 评估完成, 见 .hermes/llms-from-scratch-devour.md (学习型资产, 不移植)
- [x] 对标竞品: 企业 AI 落地服务定价/交付模式 → 见 .hermes/ai-harness-service-package.md
- [x] 设计 "AI 落地 harness" 服务包: demo → 框架 → 培训 漏斗 → 见 .hermes/ai-harness-service-package.md (Tier 0-3)
- [ ] 定价终稿 + 客户沟通脚本 (Tier 0/1 电销场景)
- [ ] 寻找 1 个 pilot 客户验证 Tier 1 交付链路

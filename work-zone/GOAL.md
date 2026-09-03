# GOAL — 双端分工推进 (2026-09-03 上线, hourly 事件驱动)

> 维护者: hourly goal 环 (Mac Hermes)。任何推进者完成后更新状态。
> owner 标注: [mac] = Hermes/Mac 执行; [pi] = VPS pi 执行; [both] = 协同。

## 当前主目标 (商业主线, 60 天现金流)
- [ ] 触达开火: 录屏配音 → Cutout.Pro → 邮件/短视频分发 (owner: mac+用户, 09-03 待配音)
- [ ] 第一个付费客户 (¥5800 Tier 0 体验): BOSS L4 名单 91 家候选 → 触达节奏 (owner: 用户主导, mac 弹药)

## 技术支撑 (演示不打脸地基)
- [ ] B1 补料: AI 治理岗位技能桥接料 (owner: [pi] 情报线, 来源: CAC 规定/JD/人社部目录) — 提案 2026-09-03-B1; **09-04-B2 建议撤回** (题自愈 0.67→1.0 零补料证伪缺料, 疑检索漂移, 归观察组待 C2 区分), 待 17:00 L3
- [ ] B2 补料: 数据出境三路径锚点速查 (owner: [pi], 来源: 个保法38条/1万人阈值) — 提案 B2; **09-04-B1 升级执行**: eval 连续 2 日 0.67 缺词"标准合同" (golden-2026-09-04.json), 整合 cn-data-outbound-three-routes.md 经 kb_refresh --no-scrape, 待 17:00 L3
- [ ] 吞噬: EU AI Act Art.50 透明度义务条款级素材 (原文/官方解读) 入库 (owner: [mac], 来源: G5 kb-gap-night 09-04, 唯一带素材边界真缺口, 覆盖 #3 并强化 #2/#8, acme 出口欧盟场景)
- [ ] C1: golden_eval 回归门禁哑火修复 — diff 锚点改固定基线 golden_baseline_20260814.json + 降幅≥0.33 边界修正 (1.0→0.67 现不触发) + 回归条目附 expect/covered (owner: [mac], 来源: P-2026-09-04-C1, 首日运行对已知回归静默实证)
- [ ] C2: kb_gap recall-gap 二级诊断 (owner: [mac]) — 提案 C2; 09-04 建议执行 (缺词定位第 3 次需人工比对 + kb_gap_report 20 天失明, 修复后先重跑), 待 17:00 L3
- [ ] C3: ytsearch 吞噬前置门禁 (owner: [mac]) — 提案 C3
- [ ] A2: 标准合同锚点题拆词进 golden_set (owner: [mac]) — 提案 A2; **09-04-A1 收口执行** (新增适用条件锚点题 + 两题补 regression_watch), 待 17:00 L3

## 自治链 (常驻, 不需人工)
- golden-eval 06:30 / proposals 07:00 / pi-review 17:00 / 夜间链 G1-G5 (状态自动滚动)

## State
goal_auto: active (2026-09-03)
last_update: 2026-09-04 07:08
audit: 07:08 巡检 — 事件 2 条: golden-2026-09-04.json (06:30 自动, 23 题 avg .986, 数据出境三方式连续第 2 日 0.67 缺词"标准合同") + proposals/2026-09-04.md (07:04 L2 环, 4 提案): B2 升级执行 / A2 收口 / C2 建议执行均获新证据, B1 建议撤回 (自愈证伪缺料, 撤回 09-03-B1), golden_eval 门禁对已知回归哑火 (diff 锚点错) → 新增 [mac] C1 修复项; 均待 17:00 L3 审批, 已同步 GOAL.md; [pi] B1/B2 状态更新 → 已推 agent-bus inbox 2 条 (ce3f5ac60d51/190fbb26a2e1)
audit_prev: 06:01 巡检 — 事件 1 条 (ae66833) 即 05:00 环自身提交回声, 已于 05:01 归档, 无新信息; 60min 内无新提交 (HEAD=ae66833, origin 无新分支/提交), REVIEW_QUEUE.md 仅 1 行 flywheel 例行漂移; 目标项维持: G5 Art.50 吞噬项待 [mac] 执行 (唯一带素材边界真缺口); 无 [pi] 任务变更, 不推送
audit_prev: 05:01 巡检 — G5 夜评 (5e7fa56) 新增 1 真缺料 Art.50 (条款级, 出口欧盟标识, 非本轮自动动作) → 新增 [mac] 吞噬项; 失败档 m2max-20260903-f001 (kb_gap docstring 调用) 已于 09-03 修正 (-m 模块模式), 夜链 exit 0 实证, 仅归档无需动作; 无 [pi] 任务变更

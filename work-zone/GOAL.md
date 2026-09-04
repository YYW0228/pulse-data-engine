# GOAL — 双端分工推进 (2026-09-03 上线, hourly 事件驱动)

> 维护者: hourly goal 环 (Mac Hermes)。任何推进者完成后更新状态。
> owner 标注: [mac] = Hermes/Mac 执行; [pi] = VPS pi 执行; [both] = 协同。

## 当前主目标 (商业主线, 60 天现金流)
- [ ] 触达开火: 录屏配音 → Cutout.Pro → 邮件/短视频分发 (owner: mac+用户, 09-03 待配音)
- [ ] 第一个付费客户 (¥5800 Tier 0 体验): BOSS L4 名单 91 家候选 → 触达节奏 (owner: 用户主导, mac 弹药)

## 技术支撑 (演示不打脸地基)
- [x] C1: 回归门禁锚点修复 (固定基线 08-14 + 整数比较) — 2026-09-04 落地, 数据出境三方式回归告警已生效 (owner: [mac])
- [x] A1: 数据出境适用条件锚点题入 golden_set (regression_watch) — 2026-09-04 (owner: [mac])
- [x] B1 补料: 数据出境三路径锚点速查 cn-data-outbound-three-routes.md 已建 + kb_refresh 入库 (owner: [mac], 2026-09-04)
- [ ] B1 撤回确认: AI 治理岗位补料 (09-03-B1) — 0.67→1.0 自愈证伪缺料判定, 已建议撤回 (pi 推送 190fbb26a2e1, 待 17:00 复盘确认)
- [ ] CI 红修复: ruff Tier1 2 错误 (scripts/golden_eval.py int(round()) 冗余 ×2, b0a306d 引入; ruff 0.16.0 本机/0.16.5 VPS 双端实证) → 修复提交 main 使 pregate-patrol 转绿 (owner: [mac], 来源: pregate-patrol bus 0a018c90e943 09-04 12:10, steer)
- [ ] 吞噬: EU AI Act Art.50 透明度义务条款级素材 (原文/官方解读) 入库 (owner: [mac], 来源: G5 kb-gap-night 09-04, 唯一带素材边界真缺口, 覆盖 #3 并强化 #2/#8, acme 出口欧盟场景)
- [x] C2: kb_gap recall-gap 二级诊断 (corpus 词频区分 recall/knowledge gap, 实测 13 recall:1 knowledge) — 2026-09-04 a32ff6e 落地入 main (owner: [mac])
- [x] C3: ytsearch 吞噬前置门禁 (标题相关性 + 产物长度, 失败案例验证) — 2026-09-04 a32ff6e 落地入 main (owner: [mac])

## 自治链 (常驻, 不需人工)
- golden-eval 06:30 / proposals 07:00 / pi-review 17:00 / 夜间链 G1-G5 (状态自动滚动)

## State
goal_auto: active (2026-09-03)
last_update: 2026-09-04 14:01
audit: 14:01 巡检 — 事件 5 条: (1) a32ff6e (13:01) C2 kb_gap 二级诊断 + C3 ytsearch 吞噬门禁实现 + 20d32b8 (13:04) merge feat/pregate-trial 入 main → C2/C3 两 [mac] 项勾 [x] 归档; (2) 80ceb4c 为 13:03 环自身回声无新信息; (3) new_failures vps-20260831-f001.json 为 08-31 已入库门禁测试痕迹 (259e9b9, pregate-gate 验证), 非真失败; (4) proposals/eval_reports 更新 = 自治链例行数据 (2337f12 已入库), 无新目标含义; (5) bus 0a018c90e943 已回执 (13:03) 不再处理; 注: a32ff6e 在 CI 红态下合入新功能 (铁律违背, 事实记录), CI 红修复项 (int(round()) ×2 仍在线 211) 保持待办首位未动; 待办维持: CI 红修复、B1 撤回 (17:00 复盘)、Art.50 吞噬; 无 [pi] 任务变更, 不推送
audit_prev: 13:03 巡检 — 事件 1 条: pregate-patrol 12:10 bus 0a018c90e943 (steer, pi→hermes) — pulse-data-engine Tier1 ruff 门槛 2 错误 (scripts/golden_eval.py int(round()) 冗余 ×2, b0a306d 引入; ruff 0.16.0 本机/0.16.5 VPS 双端实证) → 新增 [mac] CI 红修复项置待办首位 (铁律: CI 红禁新功能); 已回执该 bus delivered:true; 其余维持: B1 撤回 (17:00 复盘), Art.50 吞噬, C2/C3; 无 [pi] 新任务, 不推送
audit_prev: 12:05 巡检 — 事件 2 条 (b0a306d C1 门禁锚点修复+A1 锚点题入集落地, 6944a24 状态归档) 即上午 C1/A1/B1 完成闭环的代码+goal 提交, 任务行均已 [x], 无重复动作; main 已含归档 (c90bf3c merge 后 main=权威); 待办维持: B1 撤回确认 (17:00 L3 复盘)、Art.50 吞噬、C2/C3; 无 [pi] 任务变更, 不推送
audit_prev: 06:01 巡检 — 事件 1 条 (ae66833) 即 05:00 环自身提交回声, 已于 05:01 归档, 无新信息; 60min 内无新提交 (HEAD=ae66833, origin 无新分支/提交), REVIEW_QUEUE.md 仅 1 行 flywheel 例行漂移; 目标项维持: G5 Art.50 吞噬项待 [mac] 执行 (唯一带素材边界真缺口); 无 [pi] 任务变更, 不推送

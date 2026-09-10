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
- [x] B1 撤回确认终裁 (采纳): AI 治理岗位补料 (09-03-B1) — 0.67→1.0 自愈证伪缺料判定成立 (期间零补料零代码), 撤回补料动作, 归入 recall-gap/embedding 漂移观察组; 依据: C2 二级诊断已落地 (a32ff6e) + 09-05 golden 该题保持 1.0 — 2026-09-05 13:50 L3 用户授权提前终裁 (agent-bus 190fbb26a2e1 回执)
- [x] CI 红修复: ruff Tier1 2 错误 (scripts/golden_eval.py int(round()) 冗余 ×2, b0a306d 引入; ruff 0.16.0 本机/0.16.5 VPS 双端实证) — 2026-09-05 10:01 依据 bb17a30 归档: RUF046 冗余 int() 清除 (round 省略 ndigits 已返 int), CI 红转绿, 本机 ruff 实测 All checks passed, pregate-patrol 0a018c90e943 闭环 (owner: [mac], 来源: pregate-patrol bus 0a018c90e943 09-04 12:10, steer)
- [x] 吞噬: EU AI Act Art.50 透明度义务条款级素材 (原文/官方解读) 入库 (owner: [mac], 来源: G5 kb-gap-night 09-04, 唯一带素材边界真缺口, 覆盖 #3 并强化 #2/#8, acme 出口欧盟场景) — 2026-09-05 05:01 依据 8de37e4 G5 夜评确认闭环: eu-ai-act-art50-transparency.md (09-04 13:02 建) kb_refresh 生效, kb_gap_report 零 knowledge-gap (corpus_hits=0 剔除后保留 0), covered 16/30→20/31
- [x] C2: kb_gap recall-gap 二级诊断 (corpus 词频区分 recall/knowledge gap, 实测 13 recall:1 knowledge) — 2026-09-04 a32ff6e 落地入 main (owner: [mac])
- [x] C3: ytsearch 吞噬前置门禁 (标题相关性 + 产物长度, 失败案例验证) — 2026-09-04 a32ff6e 落地入 main (owner: [mac])
- [ ] P-2026-09-10-B1: 岗位题 3 败行动条件触发 (09-10 golden 0.33, 连续 2 期恶化 0.67→0.33; kb_gap 实证料在库 算法备案=192/伦理=64/合规=431 → recall 漂移非缺料, 聚合治分散): L2 提案 07:00 已出执行版 (锚点速查文档 + kb_refresh --no-scrape, 观察 ≥2 期), 待 17:00 L3 审批后执行 (owner: [mac], 来源: eval_reports/golden-2026-09-10.json regressions[1] + work-zone/proposals/2026-09-10.md, 2026-09-10 07:01)

## 挂起裁决 (bus 请示, 待 L3/用户, 本环不代决)
- [ ] P-2026-09-08-1: lead-gen reports/l4-20260905.json (untracked 18KB, 挂起 4 复盘日 09-05→08) 二选一裁决: 随 boss-l4 G3 提交入库 (同 md b76a6ba 模式) vs 明确 gitignore (L4 名单数据敏感, VPS 不代提交) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)
- [ ] P-2026-09-08-2: flywheel vps-20260831-f001 (门禁测试痕迹, 未 resolved 8 日) 裁决: 采纳 pi 建议标 resolved=true 或移 failures/archive/ (既有先例) vs 维持 (flywheel 漂移铁律本环不碰) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)

## 自治链 (常驻, 不需人工)
- golden-eval 06:30 / proposals 07:00 / pi-review 17:00 / 夜间链 G1-G5 (状态自动滚动)

## State
goal_auto: active (2026-09-03)
last_update: 2026-09-10 12:14
audit: 12:14 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): "commit 3a1c297 (10:01) → 空" = 监控滑窗老化回声 (goal-watch.sh 60min 窗内 3a1c297 滑出致输出转空触发 change, 空输出=窗口零事件非新信息); 硬实证: 实跑 goal-watch.sh 复现空输出 (exit 0), monitor_state hash e3b0c442…=空串 SHA256; git log 60min 窗零新提交 (HEAD=5ad46fc 11:04:52 上轮自身提交), find 11:14:03 后全仓仅 flywheel/REVIEW_QUEUE.md (12:00:46 L1 cluster.py 例行再生, diff 仅时间戳注释行, 队列 0 待审, 漂移维持不碰), failures/proposals/evals 60min 窗零命中, lead-gen HEAD 929b1a9 无新提交, 录制仍 09-02 两版未动 (record-demo-13q.sh 未提交修正维持不碰); 12:14 实查 VPS: inbox 14 条全 "delivered": true 零未决 (grep -L 实证), inbox/replies 60min 窗零新文件, bus git 最新 09-02 (b5d2152); 注: 输出已转空态, 空 vs 空静默, 本轮自身提交将回填下轮窗口; 下一预期事件: 17:00 pi-review (proposals 7 条 + P-2026-09-10-B1 审批点); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), P-2026-09-10-B1 (待 17:00 L3 审批, 本环不代决), 挂起裁决 P-2026-09-08-1/2 (待 L3); 无目标勾选/新增 (例行回声, 不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 09:01 行 (已消费回声, git 历史可溯)
audit_prev: 11:01 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): commit 3a1c297 (10:01) = 上一轮环自身回声 (其 audit 已完整处理: inbox 14 零未决已收尾/GC 已执行), 无新信息; 实证: git log 10:05 后无新提交 (HEAD=3a1c297), find 10:06 后变动文件 5 个全为噪声 (sync 11:03 stash restore 刷新 ×2 / check_goal 自身 offset / diag·err 日志, 无新编辑), lead-gen 无新提交 (HEAD 929b1a9), 录制仅 09-02 两版未动, sync-all 16 仓 All up to date (hermes-brain pulled=09-07 存量 chore); 11:01 实查 VPS: inbox 14 条全 delivered:true 零未决 (grep 实证), replies/ 最新 09-08 无新, bus git 最新 09-02 (b5d2152) 无新提交, outbox 空; 下一预期事件: 17:00 pi-review (proposals 7 条 + P-2026-09-10-B1 审批点); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), P-2026-09-10-B1 (待 17:00 L3 审批, 本环不代决), 挂起裁决 P-2026-09-08-1/2 (待 L3); 无目标勾选/新增 (例行回声, 不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 08:01 行 (已消费回声, git 历史可溯)
audit_prev: 10:01 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): commit 9596fb7 (09:01) = 上一轮环自身回声 (其 audit 已完整处理: inbox 14 零未决已收尾/GC 已执行), 无新信息; 实证: git log 09:12 后无新提交 (HEAD=9596fb7), find 09:12:45 后全域零新文件; 10:01 实查 VPS: inbox 14 条全 delivered:true 零未决 (grep 实证), replies/ 最新 09-08 无新, bus git 最新 09-02 (b5d2152) 无新提交; 下一预期事件: 17:00 pi-review (proposals 7 条 + P-2026-09-10-B1 审批点); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), P-2026-09-10-B1 (待 17:00 L3 审批, 本环不代决), 挂起裁决 P-2026-09-08-1/2 (待 L3); 无目标勾选/新增 (例行回声, 不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 07:01 行 (已消费回声, git 历史可溯)

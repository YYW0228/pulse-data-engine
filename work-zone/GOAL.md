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
- [ ] P-2026-09-10-B1: 岗位题 3 败行动条件触发 (09-10 golden 0.33, 连续 2 期恶化 0.67→0.33; kb_gap 实证料在库 算法备案=192/伦理=64/合规=431 → recall 漂移非缺料, 聚合治分散): L2 提案 07:00 已出执行版 (锚点速查文档 + kb_refresh --no-scrape, 观察 ≥2 期), 待 17:00 L3 审批后执行〔09-10 晚链失败, 无执行痕迹, 维持待批〕 (owner: [mac], 来源: eval_reports/golden-2026-09-10.json regressions[1] + work-zone/proposals/2026-09-10.md, 2026-09-10 07:01)
- [ ] 晚链失败修复: 晚报 trio-evening 连续失败 4 日 (09-07→09-10: idle 2084/2289/1986s ×3 + Connection ×1) + 09-10 晚窗口 goal-loop ×3、pi-review 17:04 同源失败 (provider 抖动; 修复向: 超时/重试参数 + cron 连败告警) (owner: [mac], 来源: 5abc520452bc/f518e9340b6a/935238ade174 09-10 输出, 2026-09-11 00:15 巡检)
- [ ] 素材链断供恢复: 夜批 G1 空转第 7 日 (队列 8/8 全消费, 自 09-04 零新料, 管道健康非故障) — 补 1-2 选题入 data/course_gaps.yaml (候选已列: Karpathy Intro to LLMs / 提问力·BEST 对照源 / DeepLearning.AI 系列) → topics --generate → 次夜 G1 自动恢复吞噬 (owner: [mac]+用户, 来源: G1 夜批报告 e92ea70524f6, 2026-09-11 02:05)

## 挂起裁决 (bus 请示, 待 L3/用户, 本环不代决)
- [ ] P-2026-09-08-1: lead-gen reports/l4-20260905.json (untracked 18KB, 挂起 4 复盘日 09-05→08) 二选一裁决: 随 boss-l4 G3 提交入库 (同 md b76a6ba 模式) vs 明确 gitignore (L4 名单数据敏感, VPS 不代提交) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)
- [ ] P-2026-09-08-2: flywheel vps-20260831-f001 (门禁测试痕迹, 未 resolved 8 日) 裁决: 采纳 pi 建议标 resolved=true 或移 failures/archive/ (既有先例) vs 维持 (flywheel 漂移铁律本环不碰) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)

## 自治链 (常驻, 不需人工)
- golden-eval 06:30 / proposals 07:00 / pi-review 17:00 / 夜间链 G1-G5 (状态自动滚动)

## State
goal_auto: active (2026-09-03)
last_update: 2026-09-11 03:04
audit: 03:04 巡检 (09-11, 事件驱动唤醒) — 事件 2 条: ① monitor diff ("fbb0c76 行" → "0febded 行") = 环自身回声 #2: 上轮提交 0febded (02:08:38) 入 60min 窗, fbb0c76 (01:05:20) 滑出; 双证: 存储快照 monitor_last_output.txt 实算 sha256 5de760f4… = monitor_state (匹配), 实跑 goal-watch 输出 strip 后 219B 与快照 cmp 逐字节同构; 下轮 04:00 预期本轮提交回填 = 回声延续; ② 夜链 G3 (night-g3-vps-pi-leadgen 321f2871f441, 02:30:07 触发 → 02:34:33 完成): A级 91 保持 (532 快照硬过滤 → 91, 排除 4, 新增 0/流失 0), 基石 2 家在位; 报告 boss-l4-refresh-20260911.md 提交 a10e4af (本机实查 = lead-gen HEAD = origin/main, 产物 sha256 fadef936… 与 G3 报一致), VPS 只读执行零副作用; 快照 491d860b 冻结第 7 轮 (08-31 18:20 后无新采集), 待 09:00 boss-verify-resume 链解锁; 硬实证: executions 02:00 后零失败 (G1 02:04:53 / G3 02:34:33 / 上轮 02:08:55 全 completed, 本轮 running; incidents 无新增, 最新 09-10 19:18), VPS inbox 15 全 delivered:true 零未决 + 65min 零新, replies 零新, bus git b5d2152 未动, 本机仓 02:08 后零新提交 (HEAD=0febded); 夜链余程: 04:30 G5 / 09:00 汇总 / 09:35 planner; 待办维持: 触达开火/付费客户/P-2026-09-10-B1 (待 17:00 L3)/晚链失败修复/素材链断供恢复/挂起 P-08-1,2; 无 [pi] 任务不推送; 本轮 GC: 截断 audit_prev 00:15 行
audit_prev: 02:06 巡检 (09-11, 事件驱动唤醒) — 事件 2 条: ① monitor diff ("0cc7652 + bus 行" → "fbb0c76 行") = 环自身回声: 上轮提交 fbb0c76 (01:05:20) 入 60min 窗, 0cc7652 (00:21:18) 与 bus flip (00:20) 滑出; 双证: monitor_state.last_output_hash 5c2f1ec3… = 存储快照实算 sha256 (匹配), 02:06 实跑 goal-watch 输出已转空 (fbb0c76 滑出, e3b0c442… 空串), 下轮 03:00 预期老化回声; ② 夜链 G1 (night-g1-material-factory e92ea70524f6, 02:00 触发 → 02:04:53 完成) 空转第 7 日: 队列 8/8 全 done_at (最新 09-03T19:14Z), topics --generate 实跑 0 新候选 (真缺口 0), 双端 llama 8080 UP, compliance.duckdb 1065 chunks 复核无缺失 — 断供=需求侧待补, 已新增目标项「素材链断供恢复」([mac]+用户); 硬实证: git log 70min 零新提交 (HEAD=fbb0c76=origin/main 同步), 仓内 find 65min 仅 GOAL.md 自身, 本机 executions 01:06 后仅本 job (running) + G1 (completed) 零失败, VPS inbox/replies 零新 + grep -L 零未决 (最近例行 00:10 patrol / 00:20 selfheal); 夜链余程 enabled: 02:30 G3 / 04:30 G5 / 09:00 汇总 / 09:35 planner; 待办维持: 触达开火/付费客户/P-2026-09-10-B1 (待 17:00 L3)/晚链失败修复/挂起 P-08-1,2; 无 [pi] 任务不推送; 本轮 GC: 截断 audit_prev 15:00 行
audit_prev: 01:01 巡检 (09-11, 事件驱动唤醒) — 事件 1 条 (monitor diff: "bus 行" → "+commit 0cc7652 行"): 环自身回声 (上轮提交 0cc7652 (00:21:18) 进入 60min 窗; bus 072a5bfe358d flip mtime (00:20) 仍在窗; 下轮 02:00 tick 时 bus 行滑出 + 本轮提交回填 = 回响延续), 零新信息; 硬实证零新事件: git log 70min 仅 0cc7652 (=HEAD=origin/main 同步), find 65min failures/proposals/evals 零命中, lead-gen 929b1a9 无新提交; VPS: inbox -mmin -65 仅 flip 文件 (delivered:true, grep -L 零未决), replies 零新, 例行 00:10 pregate-patrol Tier1 5/5 零 blocker + 00:20 selfheal 三无 (系统健康证据); 本机 executions 21:00 后零非 completed (21:32/22:00/23:00 no_change 秒退 + 00:00–00:21 七 job 全 completed), running 唯一=本轮; 哈希实证: 实跑 goal-watch.sh, 原始输出去首尾空白后 sha256 f624ec2b… = monitor_state (存储快照同构); 下一预期事件: 02:00 起夜链 / 06:30 golden / 17:00 pi-review (含 B1 审批点); 待办维持: 触达开火/付费客户/P-2026-09-10-B1 (维持待批)/晚链失败修复 ([mac])/挂起 P-08-1,2; 无 [pi] 任务不推送; 本轮 GC: 截断 audit_prev 13:01 行

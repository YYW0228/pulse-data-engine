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

## 挂起裁决 (bus 请示, 待 L3/用户, 本环不代决)
- [ ] P-2026-09-08-1: lead-gen reports/l4-20260905.json (untracked 18KB, 挂起 4 复盘日 09-05→08) 二选一裁决: 随 boss-l4 G3 提交入库 (同 md b76a6ba 模式) vs 明确 gitignore (L4 名单数据敏感, VPS 不代提交) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)
- [ ] P-2026-09-08-2: flywheel vps-20260831-f001 (门禁测试痕迹, 未 resolved 8 日) 裁决: 采纳 pi 建议标 resolved=true 或移 failures/archive/ (既有先例) vs 维持 (flywheel 漂移铁律本环不碰) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)

## 自治链 (常驻, 不需人工)
- golden-eval 06:30 / proposals 07:00 / pi-review 17:00 / 夜间链 G1-G5 (状态自动滚动)

## State
goal_auto: active (2026-09-03)
last_update: 2026-09-11 01:01
audit: 01:01 巡检 (09-11, 事件驱动唤醒) — 事件 1 条 (monitor diff: "bus 行" → "+commit 0cc7652 行"): 环自身回声 (上轮提交 0cc7652 (00:21:18) 进入 60min 窗; bus 072a5bfe358d flip mtime (00:20) 仍在窗; 下轮 02:00 tick 时 bus 行滑出 + 本轮提交回填 = 回响延续), 零新信息; 硬实证零新事件: git log 70min 仅 0cc7652 (=HEAD=origin/main 同步), find 65min failures/proposals/evals 零命中, lead-gen 929b1a9 无新提交; VPS: inbox -mmin -65 仅 flip 文件 (delivered:true, grep -L 零未决), replies 零新, 例行 00:10 pregate-patrol Tier1 5/5 零 blocker + 00:20 selfheal 三无 (系统健康证据); 本机 executions 21:00 后零非 completed (21:32/22:00/23:00 no_change 秒退 + 00:00–00:21 七 job 全 completed), running 唯一=本轮; 哈希实证: 实跑 goal-watch.sh, 原始输出去首尾空白后 sha256 f624ec2b… = monitor_state (存储快照同构); 下一预期事件: 02:00 起夜链 / 06:30 golden / 17:00 pi-review (含 B1 审批点); 待办维持: 触达开火/付费客户/P-2026-09-10-B1 (维持待批)/晚链失败修复 ([mac])/挂起 P-08-1,2; 无 [pi] 任务不推送; 本轮 GC: 截断 audit_prev 13:01 行
audit_prev: 00:15 巡检 (09-11, 事件驱动唤醒) — 事件 2 条: ① monitor diff (空 → bus_requests 行): bus 新文件 072a5bfe358d (pi daily-review 09-10, 09-10 23:30 写入, 唯一未决) 本轮消费+回执 (delivered:false→true, flip 回显 + grep -L 零命中双实证); 内容与 VPS daily-2026-09-10.md 一致: 16 提交/3 仓 (pulse 14 + hermes-brain 1 + lead-gen 1)/0 bus/巡防 Tier1 5/5/CI success/flywheel 3 未解析; ② 附记 (补记 09-07 起晚报连败链, 前轮未记录): 09-10 API 不稳定窗口 14:36–19:18 共 5 job 失败 — goal-loop ×3 (14:36 idle 1947s〔前轮已记〕/16:48 idle 1247s/17:15 Connection error), vps-pi-daily-review 17:04 (Connection error → 缺 review-2026-09-10.md, 数据由 23:30 自动版覆盖, failure_streak=1), trio-evening 19:18 (idle 1986s → 晚报连续失败第 4 日 09-07→09-10〔同源: 09-07/08 idle 2084s/2289s + 09-09 Connection〕, failure_streak=4, 用户 09-06 后无晚间 plan); 环侧: 15:03 后零提交 = 3 失败 + 18:28–23:00 六次 no_change 抑制 (正常静默), 空窗 15:03→00:15 对应 pi P-2026-09-09-1 观察; 恢复实证: 00:01 trio-health 三机全绿 + 00:14 intel 班正常 + 本轮正常; 已新增目标项「晚链失败修复」(owner [mac]); 下一预期事件: 今日 02:00 起 09-11 夜链 / 06:30 golden / 17:00 pi-review (含 B1 审批点); 待办维持: 触达开火/付费客户/P-2026-09-10-B1 (维持待批)/挂起 P-08-1,2; 无 [pi] 任务不推送; 本轮 GC: 截断 audit_prev 12:14 行 (已消费回声, git 历史可溯)
audit_prev: 15:00 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): "commit be0877a (13:01) → 空" = 监控滑窗老化回声 (60min 窗内 be0877a 于 15:00 tick 滑出致输出转空, 空=窗内零事件非新信息); 异常附记: 14:00 轮次 (started 14:03:32) API 停滞超时失败 (14:36:19 status=failed, idle 1947s>1200s, waiting for non-streaming API response, failure_streak=1, 无提交无推送 = 14:xx 心跳缺失), 本轮 15:00:41 已正常恢复 (本提交即恢复证据); 硬实证: 实跑 goal-watch.sh 复现空输出 (exit 0), monitor_state last_output_hash e3b0c442…=空串 SHA256, last_changed_at 15:00:44; git log 13:05 后零新提交 (HEAD=be0877a 13:05:46 上轮自身提交), find -newermt 13:02 全仓仅 work-zone/GOAL.md 一处 (上轮自身编辑); lead-gen HEAD 929b1a9 (02:51 G3) 无新提交, recordings 仅 09-02 两版未动; cron outputs 13:05 后仅本 job 14:36 失败记录, 无其他 job 新事件; 15:0x 实查 VPS: inbox 14 条全 "delivered": true 零未决 (分布 14×true + grep -L 零命中), inbox/replies 120min 窗零新文件, replies 最新 09-08 (61ca64b66aca), bus git 最新 b5d2152 (09-02); 下一预期事件: 17:00 pi-review (proposals 7 条 + P-2026-09-10-B1 审批点); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), P-2026-09-10-B1 (待 17:00 L3 审批, 本环不代决), 挂起裁决 P-2026-09-08-1/2 (待 L3); 无目标勾选/新增 (老化回声+上轮超时均非项目状态变更, 不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 11:01 行 (已消费回声, git 历史可溯)

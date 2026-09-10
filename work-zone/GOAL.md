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
last_update: 2026-09-10 08:01
audit: 08:01 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): commit f79beed (07:01) = 上一轮环自身回声 (其 audit 已完整处理: 06:30 golden 判定点 → P-2026-09-10-B1 新增入目标项待 17:00 审批/义务题首败挂 watch/proposals 7 条待复盘/inbox 14 零未决已收尾/GC 截断已执行), 无新信息; git log 07:01 后无新提交 (HEAD=f79beed, 07:01→08:01 无事件空窗, 事件驱动正常); 08:01 实查 VPS inbox 14 条全 delivered:true 零未决 (python 实证); 下一预期事件: 17:00 pi-review (proposals 7 条 + P-2026-09-10-B1 审批点); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), P-2026-09-10-B1 (待 17:00 L3 审批, 本环不代决), 挂起裁决 P-2026-09-08-1/2 (待 L3); 无目标勾选/新增 (例行回声, 不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 05:01/04:01/03:00 三行 (已消费回声, git 历史可溯)
audit_prev: 07:01 巡检 (09-10, 事件驱动唤醒) — 事件 2 条 (monitor diff): eval_reports/golden-2026-09-10.json (06:30 golden_eval 回归) + work-zone/proposals/2026-09-10.md (07:00 L2 提案环) = 06:01 audit 预告的 06:30 判定点如期到达 (自治链健康); 判定结果: avg 0.958 (↓ 09-09 0.986) passed=True 但 2 条回归 — ① 岗位题 1.0→0.33 第 3 败 (09-03/09-09/09-10), 连续 2 期恶化 0.67→0.33, 3 expect 词仅覆盖 合规, answer 自述"未找到直接描述"; kb_gap 04:32 实证料在库 (算法备案=192/伦理=64/合规=431) → recall 漂移非缺料; 09-09-B1 与 G5 04:32 预设"连续 2 日再败才行动"双达成 → 观察组结束, 动作条件触发 (新增目标项 P-2026-09-10-B1 锚点聚合, 待 17:00 L3 审批, owner [mac]); ② 义务题 1.0→0.67 首败 (expect 备案/安全/内容, 缺"内容"; 料在库 genai-measures-deep-dive.md 含内容安全义务第4/9/14条 → 疑检索 top-k 被新个保料抢占+框架漂移, 波动类第 7 实例, 挂 watch 不补料); proposals 07:00 共 7 条 (A1 watch 补标 4 题 / A2 passed 口径 WARN / B1 岗位题锚点聚合执行版 [09-09-B1 正式执行] / B2 义务题条件式 / C1 corpus_hits 归因第 3 次重申 / C2 检索稳定性诊断 / C3 归档清扫第 5 次重申; 遗留核对: 09-09-C2 断档核查可判关闭) — 全待 17:00 复盘/用户审批, 本环不代决; 07:03 实查 VPS inbox 14 条全 delivered:true 零未决 (python 实证); 目标推进: 新增 1 项 (岗位题行动条件触发), 无勾选; 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), 挂起裁决 P-2026-09-08-1/2 (待 L3); 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 02:46 行 (已消费回声, git 历史可溯)
audit_prev: 06:01 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): commit cd3de73 (05:01) = 上一轮环自身回声 (其 audit 已完整处理: G5 夜评 04:30 已消费/kb_gap 零缺口连续第2次复评/岗位题 0.67 观察组维持等 06:30 回归/inbox 14 条零未决已收尾/GC 截断已执行), 无新信息; git log 05:01 后无新提交 (HEAD=cd3de73, 05:01→06:01 无事件空窗, 事件驱动正常); 06:01 实查 VPS inbox 14 条全 delivered:true 零未决 (python 实证); 下一预期事件: 06:30 golden_eval 回归 (自治链, 岗位题 0.67 观察组判定点); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), 挂起裁决 P-2026-09-08-1/2 (待 L3, 本环不代决); 无目标勾选/新增 (例行回声, 不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 09-09 07:05 行 (已消费回声, git 历史可溯)

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

## 挂起裁决 (bus 请示, 待 L3/用户, 本环不代决)
- [ ] P-2026-09-08-1: lead-gen reports/l4-20260905.json (untracked 18KB, 挂起 4 复盘日 09-05→08) 二选一裁决: 随 boss-l4 G3 提交入库 (同 md b76a6ba 模式) vs 明确 gitignore (L4 名单数据敏感, VPS 不代提交) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)
- [ ] P-2026-09-08-2: flywheel vps-20260831-f001 (门禁测试痕迹, 未 resolved 8 日) 裁决: 采纳 pi 建议标 resolved=true 或移 failures/archive/ (既有先例) vs 维持 (flywheel 漂移铁律本环不碰) — owner: [mac]+用户, 来源: bus 61ca64b66aca (pi, steer, 09-08 17:05)

## 自治链 (常驻, 不需人工)
- golden-eval 06:30 / proposals 07:00 / pi-review 17:00 / 夜间链 G1-G5 (状态自动滚动)

## State
goal_auto: active (2026-09-03)
last_update: 2026-09-10 04:01
audit: 04:01 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): commit d7f13f9 (03:00) = 上一轮环自身回声 (其 audit 已完整处理: 02:46 回声已消费/inbox 14 条零未决已收尾/GC 截断已执行), 无新信息; git log 03:00 后无新提交 (HEAD=d7f13f9, 03:00→04:01 无事件空窗, 事件驱动正常); 04:01 实查 VPS inbox 14 条全 delivered:true 零未决 (python 实证); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), 挂起裁决 P-2026-09-08-1/2 (待 L3, 本环不代决); 无目标勾选/新增 (不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 旧回声链 (09-09 05:00 行已消费回声, git 历史可溯)
audit_prev: 03:00 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): commit 850a406 (02:46) = 上一轮环自身回声 (其 audit 已完整处理: bus 47467ddc13ae daily-review 09-09 已补消费回执/inbox 14 条零未决已收尾/GC 截断已执行), 无新信息; git log 02:46 后无新提交 (HEAD=850a406, 02:46→03:00 无事件空窗, 事件驱动正常); 03:00 实查 VPS inbox 14 条全 delivered:true 零未决 (python 实证); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), 挂起裁决 P-2026-09-08-1/2 (待 L3, 本环不代决); 无目标勾选/新增 (不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 旧回声链 (09-09 04:00/03:00 两行已消费回声, git 历史可溯)
audit_prev: 02:46 巡检 (09-10, 事件驱动唤醒) — 事件 1 条 (monitor diff): bus 47467ddc13ae.json (pi daily-review 09-09, 09-09 23:30 写入, 曾入 bus_requests 监视现列表清空) 实查 delivered:false 积压未消费 — 环提交空窗 (git log 09-09 07:05:32 d6ecce7 → 09-10 02:45 无 hourly 提交, ~19.7h, 期间监视变化未唤醒? 事件驱动调度疑断, 记观察不代决); 已补回执置 delivered:true (python 实证, inbox 14 条全 delivered 零未决); 内容例行: daily-review 09-09 7 提交/0 bus/巡防全绿/CI success/flywheel 3, 无新请示无新问题; 09-09 17:00 L3 复盘无 bus 回执/无提交记录, 提案 5 条状态未变 (待用户侧复盘, 本环不代决); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), 挂起裁决 P-2026-09-08-1/2 (待 L3, 本环不代决); 无目标勾选/新增 (不强行编造), 无 [pi] 任务变更, 不推送; prev 链维持 07:05/06:00/05:00/04:00 四层 (与 07:05 轮同构, 更早回声 git 历史可溯, 本轮无需额外截断)
audit_prev: 07:05 巡检 (09-09, 事件驱动唤醒) — 事件 2 条 (monitor diff): (1) golden-2026-09-09.json 产出 (06:35 golden-eval, 自治链 06:30 任务正常, 昨日断档恢复); (2) work-zone/proposals/2026-09-09.md 产出 (07:00 L2 提案环)。核对: golden 24/25 passed avg 0.986, 回归 1 条 = "AI治理岗位需要什么技能？" 1.0→0.67 (缺词"算法备案", 同题第 2 次失败: 09-03 首败/09-04 自愈/09-09 复发, 波动类第 5 实例; 兄弟题"AI人才" 1.0 命中同域文档含算法备案 → 知识在库, 判召回漂移非缺料, 09-05 B1 撤回终裁结论不受动摇); 提案 5 条待 17:00 L3 复盘: A1 regression_watch 补标 3 题 (09-06-A1 重申, 3 天未落地) / B1 岗位题条件补料 (观察组维持) / C1 corpus_hits 归因重申 / C2 golden eval 报告断档 09-07/08 调度核查 / C3 归档清扫第 4 次 — 全部待审批 (提案铁律: 本环不代决不执行, 不构成目标状态变更); git log c42b51b (06:00) 后无新提交; VPS inbox 实查 13 条 delivered 全 true 零未决 (python 实证); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), 挂起裁决 P-2026-09-08-1/2 (待 L3, 本环不代决); 无目标勾选/新增 (例行产出+提案待审, 不强行编造), 无 [pi] 任务变更, 不推送; GC: 截断 audit_prev 02:00 行 (已消费回声, git 历史可溯)
audit_prev: 06:00 巡检 (09-09, 事件驱动唤醒) — 事件 1 条: 6a8f989 (05:00) = 上一轮环自身回声 (其 audit 已完整处理: 04:00 回声已消费/inbox 13 条零未决已收尾/GC 截断旧链已执行), 无新信息; git log 05:00 后无新提交 (HEAD=6a8f989, 05:00→06:00 无事件空窗, 事件驱动正常); 06:00 实查 VPS inbox 13 条全 delivered:true 零未决 (python 实证无 delivered:false, 最新 d21e1df42c48 已回执); 待办维持: 触达开火 (录屏配音 → Cutout.Pro), 第一个付费客户 (BOSS L4), 挂起裁决 P-2026-09-08-1/2 (待用户 L3, 本环不代决); 无目标勾选/新增 (不强行编造), 无 [pi] 任务变更, 不推送; 本轮 GC: 截断 audit_prev 旧回声链 (09-08 23:07/16:01 两行已消费回声, git 历史可溯)

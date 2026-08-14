# AR 基线 (2026-08-14, system_prompt v1.0)

> 运行: `uv run python scripts/golden_eval.py --json` (前台! 后台触发 torch ABI dlopen 崩)
> 数据: data/golden_baseline_20260814.json (v2: AR-02 修复后重跑)

| 指标 | 旧基线 (20:23) | 新基线 (22:40) |
|---|---|---|
| avg_hit_rate | **0.723** | **0.712** |
| passed (≥0.80) | ❌ | ❌ |
| 全 0% 题 | 3 (guard/未找到) | 2 (ERR 环境偶发: 现在市场最缺什么AI人才 / 欧盟数据存储) |
| guard 误伤 (golden 30 题) | 1 (区别类) | 0 |

## AR-02 结论修正 (重要)

- **表面**: "大模型服务提供者有哪些义务?" 30ms 快速拒绝 → 误判为 intent guard
- **真根因**: 该题 31ms success=True = **检索 0 命中** (知识库未覆盖"大模型服务提供者义务"主题), 非 guard
- **guard 真实误伤**: golden 第 23 题 "AI模型备案和算法备案有什么区别?" → meta (已修, 误伤 1→0)
- **检索覆盖缺口**: "大模型服务提供者义务" / "欧盟用户数据存储" 等主题 = AR-03 候选 (文档入库/检索提升)

## 失败模式观察 (新基线)

- 33% 题: 期望 3 词中命中 1-2 词 — 回答覆盖不全 (维度遗漏), 非 guard 非检索
- 2 题 ERR (0ms): eval 双模块导入 (compliance_qa vs scripts.compliance_qa) 状态干扰偶发 — 已记录, 待统一为包导入
- 检索 0 命中题 (31ms): 知识库覆盖缺口 → 高杠杆方向是**入库/检索**, 不是 prompt

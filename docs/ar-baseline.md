# AR 基线 (2026-08-14, system_prompt v1.0)

> 运行: `uv run python scripts/golden_eval.py --json` (前台!)
> 数据: data/golden_baseline_20260814.json

| 指标 | 值 |
|---|---|
| avg_hit_rate | **0.723** |
| passed (≥0.80) | ❌ false |
| samples | 2/题 (取最高) |
| 30 题分布 | 100%×10, 67%×10, 33%×4, 0%×3 (guard/未找到), 其余混合 |

失败模式观察:
- 第 8/11/15 题 0-33% 且 ~0ms — intent guard / 检索弱覆盖, 非 prompt 问题 (AR-02 候选)
- 期望要点为法规概念词, 低命中题多为回答未覆盖全部维度

# autoresearch 最小实验规格 (v1)

> 日期: 2026-08-14 | 状态: 设计定稿, 待试点 | 归属: pulse-data-engine
> 思想来源: AK autoresearch (Karpathy) — 判定为**不直接采用其仓库**, 只吸收四要素最小闭环
> 四要素: ①受约束可编辑面 ②自动可信标量指标 ③keep/discard ④program.md 宪章

## 0. 子系统裁决

**试点 = compliance_qa 问答路径** (scripts/compliance_qa.py)

裁决依据 (实测代码库):
1. **eval harness 现成**: `scripts/golden_eval.py` + `data/golden_set.json` (30 题, 人工标注期望要点) → 自动标量指标 hit_rate 直接可用, samples=2 取最高消除随机性
2. **可编辑面天然单文件封闭**: system_prompt (v1.0) / temperature (0.2/0.3/0.5) / 空回答重试 / 反应式压缩 keep 轮数 全部集中在 compliance_qa.py — 与 Karpathy「只许改 train.py」同构
3. **不变量自动可查**: llm_audit 审计链路 + audit_reconstruct.py + test_llm_audit_coverage.py 已存在
4. **业务安全**: 问答路径是合规交付的核心表面, 优化直接服务客户价值; 但改动面受控, 不碰审计本体

未选候选: compaction 独立模块 (pulse 无独立 compaction 包, 指标要新造, 成本高); guard/熔断阈值 (无现成误伤率样本集, 指标不可信).

## 1. 受约束可编辑面 (Constrained Editable Surface)

**唯一可改文件: `scripts/compliance_qa.py`**

允许改 (白名单):
| 区域 | 位置 | 约束 |
|---|---|---|
| system_prompt 模板 | ~L807 | 每次改动 bump 版本号 v1.0 → v1.1… |
| temperature | L543/L840/L918 | 0.1–0.6 区间 |
| 空回答重试策略 | `_retry_empty_answer` | 重试 ≤2 次, 升温 ≤0.2 |
| 反应式压缩 keep 轮数 | ~L933 | 3–6 轮区间 |
| top_k 检索参数 | answer() 签名 | 3–10 |

**红线 (改了就 discard, 无条件):**
- `pulse/llm_audit.py` 及一切审计调用 (audited_post / audit_compaction_* / source 标识 / 审计事件结构)
- 引用来源逻辑 (L343: 不暴露相似度/内部评分) 与防注入 (L461)
- eval / 测试 / golden_set / 其他任何文件

## 2. 不可触碰的 eval harness (prepare.py 等价物)

- **入口**: `uv run python -m scripts.golden_eval --json`
- **官方跑法 (2026-08-14 实战修正)**: `uv run python scripts/golden_eval.py --json` (脚本模式)
  - `python -m` 包模式会触发 torch dlopen ABI 崩 (py3.10 venv + torch 2.6, `_PyCode_GetVarnames` 符号缺失) — 只在部分进程状态触发, 曾误判为偶发
  - **推荐用 py3.11 eval venv 根治**: `uv venv --python 3.11 /tmp/ar-venv && uv pip install --python /tmp/ar-venv duckdb sentence-transformers httpx` → `/tmp/ar-venv/bin/python scripts/golden_eval.py` (生产 .venv 不动)
- **主指标**: golden hit_rate (期望要点覆盖命中率, samples=2 取最高)
- **次指标** (输出含 ms/题): 平均延迟; LLM 调用数 (审计日志计数)
- agent 禁止修改 golden_eval.py / golden_set.json / 相关测试
- **eval 必须走真实 LLM 路径 (2026-08-14 实战修复)**:
  - `answer(use_cache=False)`: 记忆缓存命中会返回历史答案 (1ms), 完全绕过当前 prompt — 基线/实验全部被污染。golden_eval 已强制 use_cache=False (读+写都跳过), 且不污染生产缓存
  - 偶发异常重试: torch ABI dlopen 偶发崩 (py3.10 venv) / 网络抖动 → 每 sample 重试 ≤3 次
  - 环境坑: sentence_transformers 5.x 加载时访问 HF hub 会挂起 300s+ (墙) → compliance_qa.py 已强制 HF_HUB_OFFLINE=1 + device=cpu (MPS 偶发死锁)

## 3. 指标与判定规则

**基线**: 首次运行时测定当前 v1.0 的 hit_rate / 延迟 / 调用数, 写入 `docs/ar-baseline.md`。

| 判定 | 条件 |
|---|---|
| **keep** | hit_rate ≥ 基线 +0.02 且不变量 I1–I4 全绿 且 延迟 ≤1.5×基线 且 调用数 ≤1.5×基线 |
| **discard** | 其余一切情况 → `git checkout scripts/compliance_qa.py` 还原 |
| **降级观察** | hit_rate 提升但延迟/调用数 >1.5×基线 → 记录红旗, 仍 discard |

**防过拟合**: golden_set 固定 30 题 + samples=2 取最高 + 低温固定; 改动必须可解释 (prompt 措辞/参数微调), 禁止针对具体题目的定制。MVP 局限: 30 题无 holdout, 统计力有限 — 扩到 50+ 题后加 5 题 holdout。

**keep 提交**: `git commit -m "[ar] compliance_qa <+delta> <summary>"` + 追加 `docs/ar-log.md` (改动内容/hit_rate/延迟/判定)。

## 4. 必须守住的不变量 (I1–I5, 每次判定前全跑)

| # | 不变量 | 验证命令 |
|---|---|---|
| I1 | 所有 LLM 调用经 audited_post | `uv run pytest tests/test_llm_audit_coverage.py -q` |
| I2 | 审计可重建率 100% | `uv run python -m scripts.audit_reconstruct` |
| I3 | 全量测试绿 | `uv run pytest tests/ -q` (当前 190+ passed) |
| I4 | 无孤儿压缩锁 (start 无 end) | audit_reconstruct 输出 + 日志扫描 |
| I5 | 金标不倒退 | golden_eval hit_rate ≥ 基线 |

顺序: I1–I4 全绿才允许看 I5 比较。

## 5. program.md 骨架 (人类维护的宪章, 落地为 docs/program.md)

```markdown
# program.md — compliance_qa 优化宪章 (v1)

## 目标
守住全部审计不变量, 提升金标命中率与效率。

## 硬边界
- 只允许改 scripts/compliance_qa.py 白名单区 (见 autoresearch-spec.md §1)
- 禁止触碰审计/防注入/引用逻辑; 禁止改 eval/golden_set/测试

## 本轮策略 (人类批准才可改)
1. 优先 system_prompt 措辞与结构微调 (v1.x)
2. 其次 temperature / 重试微调
3. 压缩 keep 轮数仅 3–6
4. 禁止新依赖 / 新文件 / 新 LLM 调用点

## 评价与纪律
- 主指标 golden hit_rate (samples=2); keep 阈值 +0.02
- 每轮 ≤3 次改动尝试; 单轮 ≤10 分钟
- 连续 3 轮无改进 → 停止, 等人类更新宪章
- 禁止用真实客户问题刷分; 禁止针对 golden 具体题目定制
```

## 6. 运行机制 (三阶段)

- **阶段 1 人审闭环** (现在): Hermes 执行循环: 读 program.md → 单次白名单编辑 → 跑 I1–I4 + eval → keep/discard → 写 ar-log。跑 2–3 轮验证闭环稳定后进阶段 2。
- **阶段 2 半自动** (人审验证后): 接 `scripts/meta_loop.py` 提案生成 (已有: 失败轨迹聚类 → 提案), 提案自动 eval + keep/discard, 人类只看早晨报告 + 宪章。cron 驱动 (02:00, 3 轮)。
- **阶段 3 无人值守** (eval 可靠性达标后): golden_set ≥50 题 + holdout, 才允许 overnight 无 checkpoint 跑。

## 7. 与现有工作的衔接

- **swap 原语合流**: 阶段 2+ 若目标是长驻服务 (8502) 的 runtime 行为热替换, 用 `pulse/component.py` 的 ManagedComponent (build/swap/drain + component/swap 审计) 作为 keep 的执行器 — 热替换也进审计链。MVP 阶段是离线文件编辑, git checkout 即 discard, 不需要 swap。
- **meta_loop 合流**: 失败轨迹 (compliance_metrics.jsonl/traces.jsonl) 已是现成输入, 提案机制复用, AR 补上「自动 eval + 自动 keep/discard」这半圈。
- **用户期望对齐**: 吸收速度 > 分析质量, 吞噬必须闭环到代码 — 本规格的闭环 = golden 基线实测 → 1 轮试点 → ar-log 留痕。

## 8. 风险与边界 (诚实)

- golden_set 仅 30 题, hit_rate ±0.02 的统计显著性弱 → 阶段 1 只做「明显改进/明显回归」判定, 模糊区一律 discard
- LLM 命中判定 (期望要点 in 回答) 有噪声 → samples=2 取最高已缓解, 不可消除
- 若试点 3 轮全部 discard → 说明该子系统已局部最优, 换子系统 (候选: guard 熔断阈值, 需先建误伤率样本集) 或放弃 AR

# Flywheel (代理飞轮地基)

失败痕迹 → 技能沉淀 → 全员受益 的共享状态层。规范吸收自 7 仓吞噬（详见 hermes-brain/docs/flywheel-swallow-report.md），本目录随 git 提交，经 sync-all.sh 同步到 VPS。

## 目录约定

```
flywheel/
├── failures/            # 失败痕迹 (trace-record schema, 每失败一条 JSON)
├── candidates/          # 聚类后的 pattern (cluster.py 生成, 只读)
├── REVIEW_QUEUE.md      # 人工审批队列 (cluster.py 生成)
├── metrics.jsonl        # escape-rate 度量 (追加式, 每周期一行)
├── schemas/             # JSON Schema (机器可校验)
└── examples/            # 脱敏样例
```

## trace-record 必填字段 (schema: schemas/trace-record.schema.json)

id, created_at, host, project, domain, workflow, harness, skill,
instruction, input_hash, context_tokens_before, context_tokens_after,
failure_modes, target_use, raw_input_stored(=false), caught_stage

- caught_stage: review|manual|pr —— 在哪一关逃逸(未发现), 用于 escape-rate 加权
- raw_input_stored 必须 false (隐私: 只存摘要/哈希, 不存原始输入)
- failure_modes: 从预定义 9 类模式表选 (reuse-miss/scope-creep/contract-drift/test-fraud/mock-overreach/stub-slippage/oversized-bead/missing-error-handling/integration-seam), 可扩展

## metrics.jsonl (escape-rate 度量)

每周期一行 (周频):
```json
{"period": "2026-W35", "escapes": {"review": 3, "manual": 1, "pr": 2}, "orig": 40, "escape_rate": 0.15, "qa_fails": 5, "note": ""}
```
- escape = sum(review, manual, pr); 分母 orig 排除修复类任务
- 聚合用 sum(escapes)/sum(orig), 禁止 mean(rates)
- 2+ 次才算 pattern (1 次是噪音); qa_fails 是廉价信号不计入 escape

## 聚类 (cluster.py, 零 LLM)

```
python flywheel/cluster.py            # 扫描 failures/ → Jaccard 0.3 → candidates/ + REVIEW_QUEUE.md
python flywheel/cluster.py --review   # 只刷新 REVIEW_QUEUE 状态
```
- Jaccard word_set 相似度 ≥0.3 聚类; 稳定 pattern_id = sha256(规范化文本)[:12]
- 簇 ≥2 条才成为 pattern; 输出簇名/计数/代表描述/机位分布
- 积压门禁: REVIEW_QUEUE >10 或最老 >7 天 → 顶部强制标记

## 晋升流程 (propose-never-auto-apply)

1. cluster.py 生成 candidates/ + REVIEW_QUEUE.md
2. 人工审批 (带 rationale): 通过 → 晋升为技能/规则 (RECORD/ACTUATORS 分离); 拒绝 → 标注原因
3. 晋升前回归对比: 同一批失败痕迹在旧/新配置各跑一遍, 任何下降即回滚 (threshold=0)
4. 候选技能自足性 7 项: context / AC 可验证 / file pointers / 复用指针 / 边界 / deps / 验证契约

## 反模式 (禁止)

调低阈值 / 跳过 flaky / 只改数据集不修 agent / 一轮就停 / 自动应用 LLM 生成物 / 全量 traces 落盘

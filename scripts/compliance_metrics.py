"""
scripts/compliance_metrics.py — 合规问答可观测性

记录每次问答的耗时/token/引用率/失败, 存 JSONL + 汇总报告。
呼应 Harness 方案第 4 节 (可观测性与审计)。

用法:
  uv run python -m scripts.compliance_metrics            # 汇总最近统计
  uv run python -m scripts.compliance_metrics --tail 5   # 最近5条记录
"""

import argparse
import json
import statistics
import time
from pathlib import Path

METRICS_PATH = Path("data/compliance_metrics.jsonl")


def record(
    query: str,
    ms: float,
    chunks: int,
    citations: int,
    tokens_in: int,
    tokens_out: int,
    success: bool,
    error: str = "",
    model: str = "deepseek-chat",
) -> None:
    """记录一次问答指标 (JSONL 追加)"""
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "query": query[:100],
        "model": model,
        "ms": round(ms, 1),
        "chunks": chunks,
        "citations": citations,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_estimate_usd": round(tokens_in / 1e6 * 0.27 + tokens_out / 1e6 * 1.10, 5),
        "success": success,
        "error": error[:100],
    }
    with METRICS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def summarize(limit: int = 1000) -> dict:
    """汇总最近 N 条记录"""
    if not METRICS_PATH.exists():
        return {"total": 0}

    records = []
    with METRICS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    records = records[-limit:]
    if not records:
        return {"total": 0}

    success = [r for r in records if r["success"]]
    ms_list = [r["ms"] for r in records]
    tok_in = [r["tokens_in"] for r in records]
    tok_out = [r["tokens_out"] for r in records]
    cit = [r["citations"] for r in records]
    cost = sum(r["cost_estimate_usd"] for r in records)

    return {
        "total": len(records),
        "success_rate": round(len(success) / len(records), 3),
        "avg_ms": round(statistics.mean(ms_list), 1),
        "p95_ms": round(sorted(ms_list)[int(len(ms_list) * 0.95) - 1], 1) if len(ms_list) > 1 else ms_list[0],
        "avg_tokens_in": round(statistics.mean(tok_in)) if tok_in else 0,
        "avg_tokens_out": round(statistics.mean(tok_out)) if tok_out else 0,
        "avg_citations": round(statistics.mean(cit), 1) if cit else 0,
        "total_cost_usd": round(cost, 4),
        "errors": [r["error"] for r in records if not r["success"]][:5],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tail", type=int, help="显示最近 N 条记录")
    args = parser.parse_args()

    if args.tail:
        if not METRICS_PATH.exists():
            print("暂无指标记录")
            return
        records = [json.loads(l) for l in METRICS_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]
        for r in records[-args.tail:]:
            status = "✅" if r["success"] else "❌"
            print(f"{status} [{r['ts']}] {r['query'][:40]} | {r['ms']:.0f}ms | "
                  f"{r['tokens_in']}tok→{r['tokens_out']}tok | {r['citations']}引用 | ${r['cost_estimate_usd']:.5f}")
        return

    s = summarize()
    if s["total"] == 0:
        print("暂无指标记录 — 先跑一次问答")
        return
    print("=== 合规问答可观测性 ===")
    print(f"总问答: {s['total']}")
    print(f"成功率: {s['success_rate']*100:.1f}%")
    print(f"平均耗时: {s['avg_ms']}ms (P95: {s['p95_ms']}ms)")
    print(f"平均 token: {s['avg_tokens_in']} in → {s['avg_tokens_out']} out")
    print(f"平均引用: {s['avg_citations']}")
    print(f"总成本: ${s['total_cost_usd']:.4f}")
    if s["errors"]:
        print(f"最近错误: {s['errors']}")


if __name__ == "__main__":
    main()

"""harness_evolve — 自动共进化闭环 (轨迹 → 提案 → 沙箱评估 → 落地)

设计 (对应共进化最小可运行形态):
  1. scan_metrics: 从 compliance_metrics.jsonl 提取"最差5问" (回归集)
  2. scan_patterns: 扫描 harness-devour 模式库, 对照 compliance_qa 已落地机制
  3. propose: 生成可执行变体提案 (diff 描述 + 验证用例 + 阈值)
  4. evaluate: 用回归集跑新旧 harness 对比 (引用率/耗时/loop触发)

用法:
  uv run python -m scripts.harness_evolve scan      # 盘点现状 (gap 表)
  uv run python -m scripts.harness_evolve propose   # 生成提案
  uv run python -m scripts.harness_evolve evaluate --proposal <id>  # 沙箱评估
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
METRICS = DATA_DIR / "compliance_metrics.jsonl"
PATTERNS = Path.home() / "projects" / "harness-devour" / "patterns"
QA_SRC = Path(__file__).resolve().parent / "compliance_qa.py"

# 已落地机制 → 对应模式 (人工确认的事实映射)
LANDED_MAP = {
    "reactive_compaction": "reactive_compaction",
    "token_budget": "token_budget",
    "loop_detection": "loop_detection",
    "prefix_cache": "prefix_cache_stability",
    "handoff": "handoff_summary",
    "observation_masking": "identity_scoping",
    "field_grounding": "field_level_source_grounding",
    "ratelimit": "status_code_adaptive_ratelimit",
    "retry": "turn_metric_semantics",
}

# 未落地但有明确价值的候选模式 (人工初始清单, 后续由轨迹数据驱动)
CANDIDATE_PATTERNS = ["sandbox_worker_pool", "middleware_chain", "memory_extract_consolidate"]


def load_metrics() -> list[dict]:
    if not METRICS.exists():
        return []
    return [json.loads(l) for l in METRICS.read_text().splitlines() if l.strip()]


def worst_questions(n: int = 5) -> list[dict]:
    """最差5问: 低引用 + 高耗时 + 失败, 作为回归集 (按 query 去重取最差一次)"""
    rows = load_metrics()
    scored = []
    for r in rows:
        q = r.get("query", "")
        if not q or r.get("error") in ("intent:meta", "intent:attack", "intent:probe"):
            continue  # 元问题/拒绝类不算失败
        score = 0
        if not r.get("success"):
            score += 10
        if r.get("citations", 0) == 0:
            score += 5
        if (r.get("ms") or 0) > 5000:
            score += 3
        if r.get("reactive_compact"):
            score += 2
        scored.append({"query": q, "score": score, "metric": r})
    # 按 query 去重: 保留最差一次
    best_by_q: dict[str, dict] = {}
    for s in scored:
        q = s["query"]
        if q not in best_by_q or s["score"] > best_by_q[q]["score"]:
            best_by_q[q] = s
    unique = sorted(best_by_q.values(), key=lambda x: -x["score"])
    return unique[:n]


def scan_patterns() -> list[dict]:
    """扫描模式库 → gap 表 (landed / candidate / unknown)"""
    result = []
    for pdir in sorted(PATTERNS.glob("*/index.json")):
        try:
            idx = json.loads(pdir.read_text())
            name = idx.get("name", pdir.parent.name)
            status = idx.get("status", "unknown")
            adaptation = idx.get("adaptation", "") or ""
            qa_text = QA_SRC.read_text() if QA_SRC.exists() else ""
            # 落地判定: 模式名或 adaptation 关键词出现在 QA 源码中 (空 adaptation 不参与)
            landed = bool(name and name in qa_text) or bool(
                adaptation and adaptation[:20] in qa_text
            )
            result.append({
                "name": name,
                "status": status,
                "landed_in_qa": landed,
                "category": idx.get("category", ""),
                "value": idx.get("value", ""),
                "core_idea": idx.get("core_idea", "")[:80],
            })
        except Exception:
            continue
    return result


def cmd_scan(args) -> int:
    """盘点: 模式库 vs compliance_qa 落地情况"""
    patterns = scan_patterns()
    total = len(patterns)
    landed = sum(1 for p in patterns if p["landed_in_qa"])
    migrated = sum(1 for p in patterns if p["status"] == "migrated")

    print(f"=== Harness 共进化盘点 ===")
    print(f"模式库: {total} 条 | migrated: {migrated} | compliance_qa 落地: {landed}")
    print(f"\n── 未落地模式 (gap 候选):")
    for p in patterns:
        if not p["landed_in_qa"]:
            print(f"  [{p['status']}] {p['name']} ({p['category']}, value={p['value']})")
            print(f"      {p['core_idea']}")
    return 0


def cmd_propose(args) -> int:
    """生成变体提案: 最差5问 + 未落地候选模式"""
    worst = worst_questions(args.n)
    patterns = scan_patterns()
    gaps = [p for p in patterns if not p["landed_in_qa"] and p["name"] in CANDIDATE_PATTERNS]

    print("=== 变体提案 (轨迹驱动) ===")
    print(f"\n── 回归集 (最差 {len(worst)} 问):")
    for w in worst:
        m = w["metric"]
        print(f"  [{w['score']}分] {w['query'][:40]} | cit={m.get('citations')} ms={m.get('ms')} compact={m.get('reactive_compact')}")

    print(f"\n── 可落地候选模式 ({len(gaps)}):")
    for g in gaps:
        print(f"  [{g['status']}] {g['name']}: {g['core_idea']}")

    # 输出结构化提案文件
    proposal = {
        "ts": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "regression_set": [w["query"] for w in worst],
        "candidates": [g["name"] for g in gaps],
        "threshold": {"min_citations": 1, "max_ms": 5000},
    }
    out = Path("data") / "harness_proposals.jsonl"
    out.parent.mkdir(exist_ok=True)
    with out.open("a") as f:
        f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
    print(f"\n→ 提案已追加: {out}")
    return 0


def cmd_evaluate(args) -> int:
    """沙箱评估: 用回归集跑当前 harness, 记录基线 (引用率/耗时/loop触发)

    用途: 提案落地前后各跑一次 → 对比指标 (引用率↑ 耗时↓ 即通过阈值)
    """
    import time

    from scripts.compliance_qa import answer

    worst = worst_questions(args.n)
    if not worst:
        print("无回归集 (metrics 为空?)")
        return 1

    print(f"=== 沙箱评估 (回归集 {len(worst)} 问) ===")
    results = []
    for w in worst:
        q = w["query"]
        t0 = time.time()
        try:
            r = answer(q, top_k=args.top_k)
            ms = (time.time() - t0) * 1000
            citations = r.count("文档:")
            ok = len(r) > 200 and citations > 0
            results.append({"query": q, "ms": round(ms, 1), "citations": citations, "ok": ok})
            print(f"  [{'✅' if ok else '❌'}] {q[:35]} | cit={citations} {ms:.0f}ms")
        except Exception as e:
            results.append({"query": q, "ms": 0, "citations": 0, "ok": False, "error": str(e)[:50]})
            print(f"  [❌] {q[:35]} | ERROR {str(e)[:40]}")

    cit_ok = sum(1 for r in results if r["citations"] > 0)
    avg_ms = sum(r["ms"] for r in results) / max(len(results), 1)
    print(f"\n基线: 引用率 {cit_ok}/{len(results)} | 平均耗时 {avg_ms:.0f}ms")

    # 落盘基线 (供提案对比)
    baseline = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "label": args.label or "baseline",
        "top_k": args.top_k,
        "citation_rate": cit_ok / max(len(results), 1),
        "avg_ms": round(avg_ms, 1),
        "results": results,
    }
    out = Path("data") / "harness_baselines.jsonl"
    with out.open("a") as f:
        f.write(json.dumps(baseline, ensure_ascii=False) + "\n")
    print(f"→ 基线已记录: {out} (label={baseline['label']})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness_evolve")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_scan = sub.add_parser("scan", help="盘点模式库落地情况")
    p_prop = sub.add_parser("propose", help="生成变体提案")
    p_prop.add_argument("-n", type=int, default=5, help="最差N问")
    p_eval = sub.add_parser("evaluate", help="沙箱评估 (回归集基线)")
    p_eval.add_argument("-n", type=int, default=5, help="回归集大小")
    p_eval.add_argument("--top-k", type=int, default=3, help="检索块数")
    p_eval.add_argument("--label", default=None, help="基线标签 (如 after-sandbox-worker-pool)")
    args = parser.parse_args(argv)
    if args.cmd == "scan":
        return cmd_scan(args)
    if args.cmd == "propose":
        return cmd_propose(args)
    if args.cmd == "evaluate":
        return cmd_evaluate(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())

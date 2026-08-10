"""harness_evolve — 自动共进化闭环 v2 (轨迹 → 可验证提案 → A/B 评估 → 落地)

v2 升级 (相对 v1):
  - propose: 高价值候选 → 自动生成 参数变异提案 (diff 草稿 + 验证用例 + 预期指标)
  - evaluate --proposal <id>: 应用参数变异 → 回归集 A/B 对比基线 → 通过/拒绝判定
  - apply: 已通过评估的低风险提案一键落地 (记录落地前后轨迹)
  - 闭环: 提案 → 评估结果 → 状态, 完整记录在 harness_proposals.jsonl

用法:
  uv run python -m scripts.harness_evolve scan                     # 盘点 gap
  uv run python -m scripts.harness_evolve propose                  # 生成参数变异提案
  uv run python -m scripts.harness_evolve evaluate --proposal <id> # A/B 评估
  uv run python -m scripts.harness_evolve apply --proposal <id>    # 落地已通过提案
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
METRICS = DATA_DIR / "compliance_metrics.jsonl"
PROPOSALS = DATA_DIR / "harness_proposals.jsonl"
BASELINES = DATA_DIR / "harness_baselines.jsonl"
PATTERNS = Path.home() / "projects" / "harness-devour" / "patterns"
QA_SRC = Path(__file__).resolve().parent / "compliance_qa.py"

# ── 参数变异实验目录 (人工维护: 模式 → 可调参数 + 建议值 + 理由) ──
# 每个条目: 如何临时改 compliance_qa 模块级参数做 A/B
PARAM_VARIANTS = {
    "mmr_balance": {
        "pattern": "reactive_compaction",
        "params": {"MMR_LAMBDA": 0.8},
        "rationale": "MMR 相关性权重 0.7→0.8: 更贴题但多样性略降",
        "diff": "compliance_qa.py:64  MMR_LAMBDA = 0.7 → 0.8",
        "tests": ["低相关查询引用率不降", "top_k 块来自不同文档"],
        "threshold": {"min_citation_delta": 0.0, "max_ms_increase_pct": 15},
    },
    "context_budget_up": {
        "pattern": "reactive_compaction",
        "params": {"MAX_CONTEXT_CHARS": 8000},
        "rationale": "上下文预算 6000→8000: 复杂问题更多证据",
        "diff": "compliance_qa.py:48  MAX_CONTEXT_CHARS = 6000 → 8000",
        "tests": ["复杂跨境问题引用数上升", "耗时增加 <15%"],
        "threshold": {"min_citation_delta": 0.0, "max_ms_increase_pct": 15},
    },
    "sim_threshold_strict": {
        "pattern": "field_level_source_grounding",
        "params": {"SIM_THRESHOLD": 0.6},
        "rationale": "检索阈值 0.55→0.6: 更严格, 减少噪声块",
        "diff": "compliance_qa.py:47  SIM_THRESHOLD = 0.55 → 0.6",
        "tests": ["无检索命中时优雅降级", "高相关查询不受影响"],
        "threshold": {"min_citation_delta": 0.0, "max_ms_increase_pct": 10},
    },
    "handoff_earlier": {
        "pattern": "handoff_summary",
        "params": {"HANDOFF_THRESHOLD": 6},
        "rationale": "交接阈值 8→6: 更长对话更早压缩, 控成本",
        "diff": "compliance_qa.py:50  HANDOFF_THRESHOLD = 8 → 6",
        "tests": ["长对话仍可回答", "历史注入 token 下降"],
        "threshold": {"min_citation_delta": -0.1, "max_ms_increase_pct": 10},
    },
    "large_chunk_earlier": {
        "pattern": "reactive_compaction",
        "params": {"LARGE_CHUNK_CHARS": 3000},
        "rationale": "大块转存阈值 4000→3000: 更早转存, 减少上下文膨胀",
        "diff": "compliance_qa.py:49  LARGE_CHUNK_CHARS = 4000 → 3000",
        "tests": ["大文档回答仍带引用", "平均 token_in 下降"],
        "threshold": {"min_citation_delta": 0.0, "max_ms_increase_pct": 10},
    },
}


def load_metrics() -> list[dict]:
    if not METRICS.exists():
        return []
    return [json.loads(l) for l in METRICS.read_text().splitlines() if l.strip()]


def load_proposals() -> list[dict]:
    if not PROPOSALS.exists():
        return []
    return [json.loads(l) for l in PROPOSALS.read_text().splitlines() if l.strip()]


def worst_questions(n: int = 5) -> list[dict]:
    """最差5问: 低引用 + 高耗时 + 失败, 作为回归集 (按 query 去重取最差一次)"""
    rows = load_metrics()
    scored = []
    for r in rows:
        q = r.get("query", "")
        if not q or r.get("error") in ("intent:meta", "intent:attack", "intent:probe"):
            continue
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
    best_by_q: dict[str, dict] = {}
    for s in scored:
        q = s["query"]
        if q not in best_by_q or s["score"] > best_by_q[q]["score"]:
            best_by_q[q] = s
    unique = sorted(best_by_q.values(), key=lambda x: -x["score"])
    return unique[:n]


def scan_patterns() -> list[dict]:
    """扫描模式库 → gap 表"""
    result = []
    qa_text = QA_SRC.read_text() if QA_SRC.exists() else ""
    for pdir in sorted(PATTERNS.glob("*/index.json")):
        try:
            idx = json.loads(pdir.read_text())
            name = idx.get("name", pdir.parent.name)
            status = idx.get("status", "unknown")
            adaptation = idx.get("adaptation", "") or ""
            landed = bool(name and name in qa_text) or bool(
                adaptation and adaptation[:20] in qa_text
            )
            result.append({
                "name": name, "status": status, "landed_in_qa": landed,
                "category": idx.get("category", ""), "value": idx.get("value", ""),
                "core_idea": idx.get("core_idea", "")[:80],
            })
        except Exception:
            continue
    return result


# ── 参数变异应用 (A/B 引擎核心) ──

def apply_params(params: dict, mod) -> dict:
    """临时设置 compliance_qa 模块级参数, 返回原值 (供恢复)"""
    saved = {}
    for k, v in params.items():
        if hasattr(mod, k):
            saved[k] = getattr(mod, k)
            setattr(mod, k, v)
    return saved


def run_regression(queries: list[str], top_k: int = 3) -> list[dict]:
    """跑回归集 → 结果列表 (不改代码, 用当前模块状态)"""
    from scripts import compliance_qa as qa

    results = []
    for q in queries:
        t0 = time.time()
        try:
            r = qa.answer(q, top_k=top_k)
            ms = (time.time() - t0) * 1000
            citations = r.count("文档:")
            results.append({"query": q, "ms": round(ms, 1), "citations": citations,
                            "ok": len(r) > 200 and citations > 0})
        except Exception as e:
            results.append({"query": q, "ms": 0, "citations": 0, "ok": False,
                            "error": str(e)[:50]})
    return results


def summarize(results: list[dict]) -> dict:
    cit_ok = sum(1 for r in results if r["citations"] > 0)
    avg_ms = sum(r["ms"] for r in results) / max(len(results), 1)
    return {"citation_rate": cit_ok / max(len(results), 1),
            "avg_ms": round(avg_ms, 1), "n": len(results)}


# ── 命令实现 ──

def cmd_scan(args) -> int:
    patterns = scan_patterns()
    total = len(patterns)
    landed = sum(1 for p in patterns if p["landed_in_qa"])
    migrated = sum(1 for p in patterns if p["status"] == "migrated")
    print(f"=== Harness 共进化盘点 ===")
    print(f"模式库: {total} | migrated: {migrated} | compliance_qa 落地: {landed}")
    print(f"\n── 未落地模式 (gap 候选):")
    for p in patterns:
        if not p["landed_in_qa"]:
            print(f"  [{p['status']}] {p['name']} ({p['category']}, value={p['value']})")
            print(f"      {p['core_idea']}")
    return 0


def cmd_propose(args) -> int:
    """生成参数变异提案 (从 PARAM_VARIANTS 实验目录)"""
    worst = worst_questions(args.n)
    print("=== 变体提案 (参数变异实验) ===")
    print(f"回归集: 最差 {len(worst)} 问 (已去重)")
    for w in worst:
        m = w["metric"]
        print(f"  [{w['score']}分] {w['query'][:40]} | cit={m.get('citations')} ms={m.get('ms')}")

    print(f"\n实验目录: {len(PARAM_VARIANTS)} 个参数变异")
    created = 0
    for pid, variant in PARAM_VARIANTS.items():
        proposal = {
            "id": pid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pattern": variant["pattern"],
            "params": variant["params"],
            "rationale": variant["rationale"],
            "diff": variant["diff"],
            "tests": variant["tests"],
            "threshold": variant["threshold"],
            "regression_set": [w["query"] for w in worst],
            "status": "proposed",
        }
        with PROPOSALS.open("a") as f:
            f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
        created += 1
        print(f"  + [{pid}] {variant['params']} — {variant['rationale']}")

    print(f"\n→ 已生成 {created} 个提案 → {PROPOSALS}")
    return 0


def cmd_evaluate(args) -> int:
    """A/B 评估: --proposal <id> 应用参数变异 → 回归集对比基线 → 通过/拒绝"""
    from scripts import compliance_qa as qa

    # 载入提案
    proposals = load_proposals()
    prop = next((p for p in proposals if p["id"] == args.proposal), None)
    if not prop:
        print(f"❌ 提案不存在: {args.proposal} (可执行 propose 生成)")
        return 1

    queries = prop.get("regression_set") or [w["query"] for w in worst_questions(args.n)]
    print(f"=== A/B 评估: {args.proposal} ===")
    print(f"变异: {prop['params']} | 理由: {prop['rationale']}")
    print(f"diff: {prop['diff']}")
    print(f"回归集: {len(queries)} 问\n")

    # 0. 预热 (消除模型加载/索引热身的冷启动偏差 — A/B 方法学必须)
    print("预热 (消除冷启动偏差)...")
    from scripts.compliance_qa import answer as _warmup
    _warmup("什么是算法备案", top_k=1)
    print("预热完成\n")

    # 1. 基线 (当前参数)
    base_results = run_regression(queries, top_k=args.top_k)
    base = summarize(base_results)

    # 2. 应用变异 (再次预热: 消除参数切换后的重载偏差)
    saved = apply_params(prop["params"], qa)
    try:
        _warmup("什么是算法备案", top_k=1)
        variant_results = run_regression(queries, top_k=args.top_k)
    finally:
        for k, v in saved.items():
            setattr(qa, k, v)  # 恢复

    variant = summarize(variant_results)

    # 3. 判定
    thr = prop.get("threshold", {})
    min_cit_delta = thr.get("min_citation_delta", 0.0)
    max_ms_pct = thr.get("max_ms_increase_pct", 15)
    cit_delta = variant["citation_rate"] - base["citation_rate"]
    ms_delta_pct = (variant["avg_ms"] - base["avg_ms"]) / max(base["avg_ms"], 1) * 100
    passed = cit_delta >= min_cit_delta and ms_delta_pct <= max_ms_pct

    print(f"基线:   引用率 {base['citation_rate']:.2f} | 平均 {base['avg_ms']}ms")
    print(f"变异后: 引用率 {variant['citation_rate']:.2f} | 平均 {variant['avg_ms']}ms")
    print(f"Δ引用率 {cit_delta:+.2f} (门槛 ≥{min_cit_delta}) | Δ耗时 {ms_delta_pct:+.1f}% (门槛 ≤{max_ms_pct}%)")
    print(f"\n判定: {'✅ 通过' if passed else '❌ 拒绝'}")

    # 逐问对比
    print("\n逐问:")
    for b, v in zip(base_results, variant_results):
        mark = "✅" if v["citations"] >= b["citations"] else "⚠️"
        print(f"  {mark} {b['query'][:35]} | cit {b['citations']}→{v['citations']} | {b['ms']:.0f}→{v['ms']:.0f}ms")

    # 4. 写回状态
    prop["status"] = "passed" if passed else "rejected"
    prop["evaluation"] = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "baseline": base, "variant": variant,
        "cit_delta": round(cit_delta, 3), "ms_delta_pct": round(ms_delta_pct, 1),
        "decision": "pass" if passed else "reject",
        "reason": f"cit_delta={cit_delta:+.2f} ms_delta={ms_delta_pct:+.1f}%",
    }
    lines = [json.dumps(p, ensure_ascii=False) for p in proposals]
    PROPOSALS.write_text("\n".join(lines) + "\n")
    print(f"\n→ 状态已写回: {args.proposal} = {prop['status']}")
    return 0 if passed else 2


def cmd_apply(args) -> int:
    """落地已通过评估的提案 (永久修改 compliance_qa 参数)"""
    proposals = load_proposals()
    prop = next((p for p in proposals if p["id"] == args.proposal), None)
    if not prop:
        print(f"❌ 提案不存在: {args.proposal}")
        return 1
    if prop.get("status") != "passed":
        print(f"❌ 提案未通过评估 (status={prop.get('status')}), 不落地")
        return 1

    qa_text = QA_SRC.read_text()
    for k, v in prop["params"].items():
        # 精确替换 "KEY = 旧值" → "KEY = 新值" (保留行内注释与对齐空格)
        import re
        pattern = re.compile(rf"^{k}\s*=\s*[^\n#]+", re.M)
        new_text, n = pattern.subn(f"{k} = {v} ", qa_text, count=1)
        if n == 0:
            print(f"⚠️ 未找到参数 {k} 的赋值行, 跳过")
            continue
        qa_text = new_text
        print(f"  ✅ {k} → {v}")

    QA_SRC.write_text(qa_text)
    prop["status"] = "applied"
    prop["applied_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [json.dumps(p, ensure_ascii=False) for p in proposals]
    PROPOSALS.write_text("\n".join(lines) + "\n")
    print(f"→ 已落地 {args.proposal} → 修改 {QA_SRC}")
    print("  提示: 落地后重跑 evaluate 记录新基线, 验证轨迹改善")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness_evolve")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan", help="盘点模式库落地情况")
    p_prop = sub.add_parser("propose", help="生成参数变异提案")
    p_prop.add_argument("-n", type=int, default=5, help="最差N问")
    p_eval = sub.add_parser("evaluate", help="A/B 评估提案")
    p_eval.add_argument("--proposal", required=True, help="提案 id")
    p_eval.add_argument("-n", type=int, default=5)
    p_eval.add_argument("--top-k", type=int, default=3)
    p_apply = sub.add_parser("apply", help="落地已通过提案")
    p_apply.add_argument("--proposal", required=True, help="提案 id")
    args = parser.parse_args(argv)
    if args.cmd == "scan":
        return cmd_scan(args)
    if args.cmd == "propose":
        return cmd_propose(args)
    if args.cmd == "evaluate":
        return cmd_evaluate(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())

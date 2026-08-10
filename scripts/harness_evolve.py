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
import json
import sys
import time
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
    "parallel_retrieve": {
        "pattern": "sandbox_worker_pool",
        "params": {"USE_PARALLEL": True},
        "rationale": "并行检索开关: 复杂/双库查询走进程隔离子任务 (优先级 B 成果, 1.54x 加速)",
        "diff": "compliance_qa.py  USE_PARALLEL = False → True",
        "tests": ["复杂查询引用覆盖提升", "简单查询保持薄路径", "并行失败降级串行"],
        "threshold": {"min_citation_delta": 0.0, "max_ms_increase_pct": 30},
    },
}

# ── 结构级提案 (机制插入点, 带可验证预测) ──
# 每个提案: 插入点 + 伪代码 + 可验证预测 (预期指标变化, 供 A/B 判定)
STRUCTURAL_VARIANTS = {
    "memory_extract_min": {
        "pattern": "memory_extract_consolidate",
        "mechanism": "记忆提取最小版: answer 后把 (query, citations, ok) 写入 memory 表; 下次同 query 先查记忆命中则跳过检索",
        "insert_point": "compliance_qa.answer() 开头: 查 memory_cache → 命中直接返回; 结尾: 写入 memory_cache",
        "pseudocode": """
            # answer() 开头
            hit = memory.get(query)
            if hit: return hit
            # answer() 结尾 (成功且有引用时)
            memory.put(query, answer, citations)
        """,
        "prediction": "重复查询耗时下降 ≥50% (缓存命中); 引用率不降",
        "tests": ["同 query 二次命中耗时 <1s", "不同 query 不误命中", "引用率不降"],
        "threshold": {"min_citation_delta": -0.05, "max_ms_increase_pct": 10},
    },
    "middleware_min": {
        "pattern": "middleware_chain",
        "mechanism": "中间件链最小版: 把 answer 的护栏检查 (意图分类/预算/loop) 抽成可插拔列表, 支持按查询动态开关",
        "insert_point": "compliance_qa.answer() 护栏段 → 提取为 _GUARDS 列表",
        "pseudocode": """
            _GUARDS = [intent_guard, budget_guard, loop_guard]
            for g in _GUARDS:
                stop = g(query, state)
                if stop: return stop
        """,
        "prediction": "护栏代码行数减少 + 每轮 answer 可观测 guard 命中次数 (新信号); 行为不变",
        "tests": ["意图分类拒绝仍工作", "预算闸门仍工作", "loop 检测仍工作"],
        "threshold": {"min_citation_delta": 0.0, "max_ms_increase_pct": 5},
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
        except Exception:  # noqa: S112 — 坏模式文件跳过
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
    """跑回归集 → 结果列表 (不改代码, 用当前模块状态)

    过程信号 (Process RM 轻量版):
      - loop_triggered: Loop Detection 是否触发 (重复检索模式)
      - low_confidence: 平均相似度 < 0.6 (低置信度检索)
      - empty_answer: 回答为空/过短
    """
    from scripts import compliance_qa as qa

    results = []
    for q in queries:
        t0 = time.time()
        loop = False
        low_conf = False
        empty = False
        try:
            # 检索置信度探测 (compile_context 内部评分)
            try:
                chunks = qa.compile_context(q, top_k=top_k, mask_metadata=False)
                if chunks:
                    avg_sim = sum(c.get("hits", 0) for c in chunks) / len(chunks)
                    low_conf = avg_sim < 0.6
            except Exception:
                pass

            r = qa.answer(q, top_k=top_k)
            ms = (time.time() - t0) * 1000
            citations = r.count("文档:")
            empty = len(r.strip()) < 100

            # loop 触发: 回答包含 loop 终止标记
            loop = "loop_capped" in r or "重复检索循环" in r

            results.append({"query": q, "ms": round(ms, 1), "citations": citations,
                            "ok": len(r) > 200 and citations > 0,
                            "loop_triggered": loop, "low_confidence": low_conf,
                            "empty_answer": empty})
        except Exception as e:
            results.append({"query": q, "ms": 0, "citations": 0, "ok": False,
                            "loop_triggered": False, "low_confidence": False,
                            "empty_answer": True, "error": str(e)[:50]})
    return results


def summarize(results: list[dict]) -> dict:
    cit_ok = sum(1 for r in results if r["citations"] > 0)
    avg_ms = sum(r["ms"] for r in results) / max(len(results), 1)
    n = max(len(results), 1)
    # 过程信号汇总 (Process RM)
    loop = sum(1 for r in results if r.get("loop_triggered"))
    low_conf = sum(1 for r in results if r.get("low_confidence"))
    empty = sum(1 for r in results if r.get("empty_answer"))
    return {
        "citation_rate": cit_ok / n,
        "avg_ms": round(avg_ms, 1),
        "n": len(results),
        "loop_triggered": loop,
        "low_confidence_rate": round(low_conf / n, 2),
        "empty_answer": empty,
    }


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

    print(f"\n实验目录: {len(PARAM_VARIANTS)} 个参数变异 + {len(STRUCTURAL_VARIANTS)} 个结构提案")
    created = 0
    existing_ids = {p.get("id") for p in load_proposals()}
    for pid, variant in {**PARAM_VARIANTS, **STRUCTURAL_VARIANTS}.items():
        if pid in existing_ids:
            print(f"  = [{pid}] 已存在, 跳过 (去重)")
            continue
        is_structural = pid in STRUCTURAL_VARIANTS
        proposal = {
            "id": pid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "kind": "structural" if is_structural else "param",
            "pattern": variant["pattern"],
            "rationale": variant["rationale"] if not is_structural else variant["mechanism"],
            "diff": variant["diff"] if not is_structural else variant["insert_point"],
            "tests": variant["tests"],
            "threshold": variant["threshold"],
            "regression_set": [w["query"] for w in worst],
            "status": "proposed",
        }
        if is_structural:
            proposal["pseudocode"] = variant.get("pseudocode", "")
            proposal["prediction"] = variant.get("prediction", "")
        else:
            proposal["params"] = variant["params"]
        with PROPOSALS.open("a") as f:
            f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
        created += 1
        kind = "结构" if is_structural else "参数"
        print(f"  + [{pid}] ({kind}) — {proposal['rationale'][:60]}")

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
    if prop.get("kind") == "structural":
        print(f"结构提案: {prop['rationale']}")
        print(f"插入点: {prop.get('diff', '')}")
        print(f"可验证预测: {prop.get('prediction', '')}")
        print(f"⚠️ 结构提案需手动实现后重跑 (evaluate 仅记录基线)")
        # 只记录基线, 不应用 (无 params)
        base_results = run_regression(queries, top_k=args.top_k)
        base = summarize(base_results)
        prop["status"] = "implementing"
        prop["evaluation"] = {
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "baseline": base, "decision": "pending_implementation",
            "reason": "结构提案: 基线已记录, 待手动实现后重跑对比",
        }
        lines = [json.dumps(p, ensure_ascii=False) for p in proposals]
        PROPOSALS.write_text("\n".join(lines) + "\n")
        print(f"基线: 引用率 {base['citation_rate']:.2f} | 平均 {base['avg_ms']}ms | "
              f"loop={base['loop_triggered']} 低置信={base['low_confidence_rate']}")
        print(f"→ 状态: {prop['status']} (实现后重跑 evaluate)")
        return 0

    print(f"变异: {prop.get('params', {})} | 理由: {prop['rationale']}")
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
        pattern = re.compile(rf"^{k}\s*=\s*[^\n#]+", re.MULTILINE)
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


def detect_failure_patterns(metrics: list[dict], min_samples: int = 3) -> list[dict]:
    """主动扫描轨迹 → 失败/低效模式 (优先级 C)

    模式:
      1. low_citation: 引用率 0 的 fact 查询 (知识缺口)
      2. slow_query: 耗时 > 8000ms (性能问题)
      3. repeated_fail: 同一 query 多次失败 (系统性缺陷)
    输出: [{pattern, query, score, evidence}]
    """
    from collections import Counter

    patterns: list[dict] = []
    q_counter = Counter(r.get("query", "") for r in metrics if r.get("query"))

    # 1. 低引用 (知识缺口)
    low_cit = [r for r in metrics
               if r.get("query") and r.get("citations", 0) == 0
               and r.get("error") not in ("intent:meta", "intent:attack", "intent:probe", "intent:creative")
               and r.get("success")]
    if len(low_cit) >= min_samples:
        by_q: dict[str, int] = {}
        for r in low_cit:
            by_q[r["query"]] = by_q.get(r["query"], 0) + 1
        top = max(by_q.items(), key=lambda x: x[1])
        patterns.append({
            "pattern": "low_citation", "query": top[0], "count": top[1],
            "score": min(top[1] * 5, 30), "evidence": f"{top[1]} 次零引用 (知识缺口候选)",
        })

    # 2. 高耗时
    slow = [r for r in metrics if r.get("query") and (r.get("ms") or 0) > 8000]
    if len(slow) >= min_samples:
        avg = sum(r.get("ms", 0) for r in slow) / len(slow)
        patterns.append({
            "pattern": "slow_query", "query": slow[0].get("query", ""), "count": len(slow),
            "score": 20, "evidence": f"{len(slow)} 次 >8s, 平均 {avg:.0f}ms (性能候选)",
        })

    # 3. 重复失败 (只取真实有失败的重复 query)
    repeated = [(q, c) for q, c in q_counter.items() if c >= 2 and q]
    for q, c in repeated:
        fails = [r for r in metrics if r.get("query") == q and not r.get("success")]
        if len(fails) >= 2:
            patterns.append({
                "pattern": "repeated_fail", "query": q, "count": c,
                "score": 25, "evidence": f"{q[:30]}... {len(fails)} 次失败 (系统性缺陷候选)",
            })
            break  # 只取第一个系统性缺陷

    return patterns


def auto_propose(metrics: list[dict] | None = None, top_k: int = 3) -> list[dict]:
    """自动生成提案 (优先级 C): 失败模式 → PARAM_VARIANTS 映射

    规则:
      - low_citation → sim_threshold_strict (更严阈值 → 更精准) 或 context_budget_up
      - slow_query → parallel_retrieve (并行提速) 或 large_chunk_earlier
      - repeated_fail → mmr_balance (改检索质量)
    """
    if metrics is None:
        metrics = load_metrics()
    patterns = detect_failure_patterns(metrics)

    mapping = {
        "low_citation": ["context_budget_up", "sim_threshold_strict"],
        "slow_query": ["parallel_retrieve", "large_chunk_earlier"],
        "repeated_fail": ["mmr_balance"],
    }

    # ── 元层接线: pattern 历史通过率 → 候选权重 (meta_analyze 实时统计) ──
    meta = meta_analyze()
    by_pattern: dict = {} if meta.get("empty") else meta.get("by_pattern", {})

    def _meta_weight(pid: str) -> float:
        """pattern 通过率 → 权重: ≥0.8 高优先, ≤0.3 跳过, 样本<3 中性 0.5"""
        pattern = PARAM_VARIANTS[pid]["pattern"]
        st = by_pattern.get(pattern)
        if not st or st.get("n", 0) < 3:
            return 0.5  # 样本不足: 不采信
        rate = st.get("pass_rate", 0.5)
        return 0.0 if rate <= 0.3 else rate

    created: list[dict] = []
    candidates: list[tuple[float, str, dict, dict]] = []  # (weight, pid, pattern, variant)
    for p in patterns:
        for pid in mapping.get(p["pattern"], []):
            if pid not in PARAM_VARIANTS:
                continue
            # 查是否已有同 id 提案
            existing = [x for x in load_proposals() if x["id"] == pid]
            if existing:
                continue  # 已提案过, 不重复
            weight = _meta_weight(pid)
            if weight <= 0.0:
                continue  # 元层否决: 该 pattern 历史通过率 ≤30%
            candidates.append((weight, pid, p, PARAM_VARIANTS[pid]))

    candidates.sort(key=lambda x: -x[0])  # 元层权重降序 → 高通过率模式优先
    for weight, pid, p, variant in candidates[:top_k]:
        proposal = {
            "id": pid,
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "auto_generated": True,
            "meta_weight": round(weight, 2),  # 元层: pattern 历史通过率
            "trigger": f"{p['pattern']}: {p['evidence']}",
            "pattern": variant["pattern"],
            "params": variant["params"],
            "rationale": variant["rationale"],
            "diff": variant["diff"],
            "tests": variant["tests"],
            "threshold": variant["threshold"],
            "regression_set": [x["query"] for x in worst_questions(top_k)],
            "status": "proposed",
        }
        with PROPOSALS.open("a") as f:
            f.write(json.dumps(proposal, ensure_ascii=False) + "\n")
        created.append(proposal)
    return created


def cmd_watch(args) -> int:
    """主动驱动 (优先级 C): 扫描轨迹 → 自动提案 → 可选自动 evaluate"""
    rows = load_metrics()
    patterns = detect_failure_patterns(rows)
    print(f"=== 轨迹主动扫描 (共 {len(rows)} 条) ===")
    for p in patterns:
        print(f"  [{p['pattern']}] score={p['score']} {p['evidence']}")

    if not patterns:
        print("\n无失败模式 — harness 状态健康")
        return 0

    created = auto_propose(rows)
    print(f"\n→ 自动生成 {len(created)} 个提案:")
    for c in created:
        w = c.get("meta_weight", "?")
        print(f"  + [{c['id']}] w={w} 触发: {c['trigger']}")

    if args.eval and created:
        print("\n→ 自动评估:")
        for c in created:
            print(f"  = evaluate {c['id']} ...")
        # 调用 evaluate 逻辑 (半自动: 只评估不落地)
        from scripts.harness_evolve import cmd_evaluate
        for c in created:
            cmd_evaluate(type("A", (), {"proposal": c["id"], "n": args.n, "top_k": 3})())
    return 0


def meta_analyze(proposals: list[dict] | None = None) -> dict:
    """元层最小统计: 提案通过率特征 (元学习信号)

    统计:
      - 按 kind (param/structural): 通过率
      - 按 pattern: 通过率
      - 按触发模式 (auto_generated vs manual): 通过率
    输出: 反馈给 auto_propose 排序的权重
    """
    if proposals is None:
        proposals = load_proposals()
    if not proposals:
        return {"empty": True}


    def _rate(items: list[dict]) -> dict:
        n = len(items)
        passed = sum(1 for p in items if p.get("status") == "applied")
        return {"n": n, "pass_rate": round(passed / n, 2) if n else 0.0}

    # 按 kind
    by_kind: dict[str, list[dict]] = {}
    for p in proposals:
        by_kind.setdefault(p.get("kind", "param"), []).append(p)

    # 按 pattern
    by_pattern: dict[str, list[dict]] = {}
    for p in proposals:
        by_pattern.setdefault(p.get("pattern", "?"), []).append(p)

    return {
        "total": len(proposals),
        "by_kind": {k: _rate(v) for k, v in by_kind.items()},
        "by_pattern": {k: _rate(v) for k, v in by_pattern.items()},
        "applied": sum(1 for p in proposals if p.get("status") == "applied"),
        "rejected": sum(1 for p in proposals if p.get("status") == "rejected"),
        "pending": sum(1 for p in proposals if p.get("status") not in ("applied", "rejected")),
    }


# 元层反馈: 提案类型优先级权重 (由 meta_analyze 结果动态更新)
PROPOSAL_PRIORITY: dict[str, float] = {
    "memory_extract_consolidate": 1.0,
    "sandbox_worker_pool": 0.8,
    "middleware_chain": 0.8,
    "reactive_compaction": 0.7,
    "handoff_summary": 0.5,
    "field_level_source_grounding": 0.5,
    "prefix_cache_stability": 0.6,
}


def cmd_meta(args) -> int:
    """元层: 提案通过率统计 + 优先级反馈"""
    stats = meta_analyze()
    if stats.get("empty"):
        print("无提案记录")
        return 0

    print("=== 元层统计 (提案通过率) ===")
    print(f"总提案: {stats['total']} (applied={stats['applied']} rejected={stats['rejected']} pending={stats['pending']})")
    print("\n按类型:")
    for k, v in stats["by_kind"].items():
        print(f"  {k:12} n={v['n']} 通过率={v['pass_rate']:.0%}")
    print("\n按模式:")
    for k, v in sorted(stats["by_pattern"].items(), key=lambda x: -x[1]["pass_rate"]):
        print(f"  {k:35} n={v['n']} 通过率={v['pass_rate']:.0%}")

    # 反馈: 高通过率模式 → 提权; 低通过率 → 降权
    for k, v in stats["by_pattern"].items():
        if v["pass_rate"] >= 0.8 and k in PROPOSAL_PRIORITY:
            PROPOSAL_PRIORITY[k] = min(PROPOSAL_PRIORITY.get(k, 1.0) * 1.2, 1.5)
        elif v["pass_rate"] <= 0.3 and k in PROPOSAL_PRIORITY:
            PROPOSAL_PRIORITY[k] = max(PROPOSAL_PRIORITY.get(k, 1.0) * 0.7, 0.3)
    print("\n更新后优先级:")
    for k, v in sorted(PROPOSAL_PRIORITY.items(), key=lambda x: -x[1])[:5]:
        print(f"  {k:35} {v:.2f}")
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
    p_watch = sub.add_parser("watch", help="轨迹主动扫描 → 自动提案")
    p_watch.add_argument("--eval", action="store_true", help="自动评估新提案")
    p_watch.add_argument("-n", type=int, default=5)
    sub.add_parser("meta", help="元层: 提案通过率统计 + 优先级反馈")
    args = parser.parse_args(argv)
    if args.cmd == "scan":
        return cmd_scan(args)
    if args.cmd == "propose":
        return cmd_propose(args)
    if args.cmd == "evaluate":
        return cmd_evaluate(args)
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "watch":
        return cmd_watch(args)
    if args.cmd == "meta":
        return cmd_meta(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())

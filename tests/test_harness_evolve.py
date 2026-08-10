"""harness_evolve 共进化闭环测试 — scan/propose/worst_questions 逻辑"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


@pytest.fixture
def metrics_file(tmp_path):
    """构造带重复项 + 失败样本的 metrics 数据"""
    rows = [
        {"query": "A 问题", "success": True, "citations": 2, "ms": 100, "reactive_compact": False, "error": None},
        {"query": "A 问题", "success": False, "citations": 0, "ms": 9000, "reactive_compact": True, "error": "timeout"},
        {"query": "B 问题", "success": True, "citations": 0, "ms": 6000, "reactive_compact": False, "error": None},
        {"query": "C 元问题", "success": True, "citations": 0, "ms": 0, "reactive_compact": False, "error": "intent:meta"},
    ]
    f = tmp_path / "compliance_metrics.jsonl"
    f.write_text("\n".join(json.dumps(r) for r in rows))
    return f


def test_worst_questions_dedup_and_skip_meta(monkeypatch, metrics_file):
    from scripts import harness_evolve as he

    monkeypatch.setattr(he, "METRICS", metrics_file)
    worst = he.worst_questions(n=5)
    queries = [w["query"] for w in worst]
    # A 去重 (取最差一次: failure 版), B 在内, C (meta) 被排除
    assert "A 问题" in queries
    assert "B 问题" in queries
    assert "C 元问题" not in queries
    assert len(queries) == 2
    # A 的分数应该更高 (failure + 0 cit + slow + compact)
    a = next(w for w in worst if w["query"] == "A 问题")
    assert a["score"] >= 20


def test_scan_patterns_reports_gaps(monkeypatch, tmp_path):
    """构造迷你模式库 → scan 输出 gap"""
    from scripts import harness_evolve as he

    fake_patterns = tmp_path / "patterns"
    (fake_patterns / "sandbox_worker_pool").mkdir(parents=True)
    (fake_patterns / "sandbox_worker_pool" / "index.json").write_text(json.dumps({
        "name": "sandbox_worker_pool", "status": "watch", "category": "sandbox",
        "value": "medium", "core_idea": "预 fork worker 池",
    }))
    monkeypatch.setattr(he, "PATTERNS", fake_patterns)
    monkeypatch.setattr(he, "QA_SRC", tmp_path / "empty.py")
    (tmp_path / "empty.py").write_text("# empty")

    patterns = he.scan_patterns()
    assert len(patterns) == 1
    assert patterns[0]["name"] == "sandbox_worker_pool"
    assert patterns[0]["landed_in_qa"] is False  # QA_SRC 不含该模式


def test_propose_writes_file(monkeypatch, tmp_path, metrics_file):
    from scripts import harness_evolve as he

    monkeypatch.setattr(he, "METRICS", metrics_file)
    monkeypatch.setattr(he, "PATTERNS", tmp_path / "empty_patterns")
    (tmp_path / "data").mkdir(exist_ok=True)
    monkeypatch.setattr(he, "PROPOSALS", tmp_path / "data" / "harness_proposals.jsonl")

    rc = he.cmd_propose(type("A", (), {"n": 5})())
    assert rc == 0
    proposals = he.PROPOSALS.read_text().splitlines()
    assert len(proposals) == len(he.PARAM_VARIANTS) + len(he.STRUCTURAL_VARIANTS)
    p = json.loads(proposals[0])
    assert "regression_set" in p
    assert p["threshold"]["min_citation_delta"] == 0.0


def test_apply_params_roundtrip():
    """参数变异应用/恢复 (A/B 引擎核心)"""
    import types

    from scripts import harness_evolve as he

    mod = types.SimpleNamespace(MMR_LAMBDA=0.7, MAX_CONTEXT_CHARS=6000)
    saved = he.apply_params({"MMR_LAMBDA": 0.8}, mod)
    assert mod.MMR_LAMBDA == 0.8
    assert saved == {"MMR_LAMBDA": 0.7}
    for k, v in saved.items():
        setattr(mod, k, v)
    assert mod.MMR_LAMBDA == 0.7  # 恢复


def test_summarize_rate():
    from scripts import harness_evolve as he

    s = he.summarize([
        {"citations": 2, "ms": 100}, {"citations": 0, "ms": 300},
    ])
    assert s["citation_rate"] == 0.5
    assert s["avg_ms"] == 200.0
    assert s["n"] == 2


def test_apply_requires_passed(tmp_path, monkeypatch):
    """未通过评估的提案不可落地"""
    from scripts import harness_evolve as he

    # 构造 rejected 提案
    (tmp_path / "data").mkdir(exist_ok=True)
    prop_file = tmp_path / "data" / "harness_proposals.jsonl"
    prop_file.write_text(json.dumps({
        "id": "bad", "status": "rejected", "params": {"MMR_LAMBDA": 0.9},
    }) + "\n")
    monkeypatch.setattr(he, "PROPOSALS", prop_file)
    monkeypatch.setattr(he, "QA_SRC", tmp_path / "qa.py")
    (tmp_path / "qa.py").write_text("MMR_LAMBDA = 0.7\n")

    rc = he.cmd_apply(type("A", (), {"proposal": "bad"})())
    assert rc == 1  # 拒绝落地
    assert "MMR_LAMBDA = 0.7" in (tmp_path / "qa.py").read_text()  # 未修改


def test_detect_failure_patterns():
    """轨迹主动扫描: 低引用/高耗时/重复失败 模式识别"""
    from scripts import harness_evolve as he

    metrics = [
        # 低引用 (知识缺口) ×3
        {"query": "Q1", "citations": 0, "success": True, "error": None, "ms": 100},
        {"query": "Q1", "citations": 0, "success": True, "error": None, "ms": 100},
        {"query": "Q1", "citations": 0, "success": True, "error": None, "ms": 100},
        # 高耗时
        {"query": "Q2", "citations": 2, "success": True, "error": None, "ms": 12000},
        {"query": "Q2", "citations": 2, "success": True, "error": None, "ms": 15000},
        {"query": "Q2", "citations": 2, "success": True, "error": None, "ms": 9000},
        # 重复失败
        {"query": "Q3", "citations": 0, "success": False, "error": "boom", "ms": 100},
        {"query": "Q3", "citations": 0, "success": False, "error": "boom", "ms": 100},
        # meta 类不算
        {"query": "Q4", "citations": 0, "success": True, "error": "intent:meta", "ms": 1},
    ]
    patterns = he.detect_failure_patterns(metrics, min_samples=2)
    kinds = {p["pattern"] for p in patterns}
    assert "low_citation" in kinds
    assert "slow_query" in kinds
    assert "repeated_fail" in kinds
    for p in patterns:
        assert p["score"] > 0
        assert p["evidence"]


def test_auto_propose_dedup(tmp_path, monkeypatch):
    """自动提案: 失败模式 → PARAM_VARIANTS 映射 + 去重"""
    from scripts import harness_evolve as he

    (tmp_path / "data").mkdir(exist_ok=True)
    prop_file = tmp_path / "data" / "harness_proposals.jsonl"
    monkeypatch.setattr(he, "PROPOSALS", prop_file)

    # 构造触发 low_citation 的轨迹 (3 次零引用)
    metrics = [
        {"query": "知识缺口问题", "citations": 0, "success": True, "error": None, "ms": 100},
        {"query": "知识缺口问题", "citations": 0, "success": True, "error": None, "ms": 100},
        {"query": "知识缺口问题", "citations": 0, "success": True, "error": None, "ms": 100},
    ]
    created = he.auto_propose(metrics=metrics, top_k=3)
    assert len(created) > 0
    assert all(c["auto_generated"] for c in created)
    assert all(c["status"] == "proposed" for c in created)
    # low_citation → context_budget_up / sim_threshold_strict
    ids = {c["id"] for c in created}
    assert "context_budget_up" in ids or "sim_threshold_strict" in ids

    # 第二轮: 去重 (不重复生成)
    created2 = he.auto_propose(metrics=metrics, top_k=3)
    assert len(created2) == 0


def test_meta_analyze_rates():
    """元层统计: 提案通过率特征 (EMA 时间衰减, P2)"""
    from scripts import harness_evolve as he

    proposals = [
        {"id": "a", "kind": "param", "pattern": "reactive_compaction", "status": "applied", "ts": "2026-08-01 10:00:00"},
        {"id": "b", "kind": "param", "pattern": "reactive_compaction", "status": "rejected", "ts": "2026-08-02 10:00:00"},
        {"id": "c", "kind": "structural", "pattern": "memory_extract_consolidate", "status": "applied", "ts": "2026-08-03 10:00:00"},
        {"id": "d", "kind": "structural", "pattern": "middleware_chain", "status": "applied", "ts": "2026-08-04 10:00:00"},
    ]
    stats = he.meta_analyze(proposals)
    assert stats["total"] == 4
    assert stats["applied"] == 3
    assert stats["rejected"] == 1
    # EMA α=0.4 时间衰减: applied,rejected → 0.5→0.7→0.42 → round(0.42,2)
    assert stats["by_kind"]["param"]["pass_rate"] == 0.42
    # structural: applied,applied → 0.5→0.7→0.82
    assert stats["by_kind"]["structural"]["pass_rate"] == 0.82
    # pattern 级 (2 样本: applied,rejected → 0.42)
    assert stats["by_pattern"]["reactive_compaction"]["pass_rate"] == 0.42
    assert stats["by_pattern"]["memory_extract_consolidate"]["pass_rate"] == 0.7  # 1 样本 → 0.5→0.7


def test_meta_ema_recency_dominates():
    """P2: EMA 防早期数据主导 — 早期失败+近期成功 → 通过率高于简单平均"""
    from scripts import harness_evolve as he

    proposals = [
        {"id": "old1", "kind": "param", "pattern": "reactive_compaction", "status": "rejected", "ts": "2026-06-01 10:00:00"},
        {"id": "old2", "kind": "param", "pattern": "reactive_compaction", "status": "rejected", "ts": "2026-06-15 10:00:00"},
        {"id": "new1", "kind": "param", "pattern": "reactive_compaction", "status": "applied", "ts": "2026-08-10 10:00:00"},
    ]
    stats = he.meta_analyze(proposals)
    rate = stats["by_pattern"]["reactive_compaction"]["pass_rate"]
    # 简单平均 = 0.33; EMA: 0.5→0.3→0.18→0.51 → 近期成功被放大
    assert rate > 0.33, f"EMA 应放大近期成功: {rate}"
    assert rate == 0.51
    # 反向: 早期成功+近期失败 → EMA 低于简单平均 (近期失败被放大)
    proposals2 = [
        {"id": "old1", "kind": "param", "pattern": "x", "status": "applied", "ts": "2026-06-01 10:00:00"},
        {"id": "old2", "kind": "param", "pattern": "x", "status": "applied", "ts": "2026-06-15 10:00:00"},
        {"id": "new1", "kind": "param", "pattern": "x", "status": "rejected", "ts": "2026-08-10 10:00:00"},
    ]
    stats2 = he.meta_analyze(proposals2)
    rate2 = stats2["by_pattern"]["x"]["pass_rate"]
    assert rate2 < 0.67, f"EMA 应放大近期失败: {rate2}"
    assert rate2 == 0.49  # applied,applied,rejected: 0.5→0.7→0.82→0.492


def test_meta_ema_small_sample_neutral():
    """P2: 单样本 EMA 反映最近结果 (0.5→0.7), 采信门槛由 auto_propose 负责"""
    from scripts import harness_evolve as he

    stats = he.meta_analyze([{"id": "a", "kind": "param", "pattern": "x", "status": "applied", "ts": "2026-08-01 10:00:00"}])
    assert stats["by_pattern"]["x"]["pass_rate"] == 0.7


def test_meta_updates_priority():
    """元层反馈: 高通过率提权 / 低通过率降权 (EMA 语义: ≥3 样本才采信)"""
    from scripts import harness_evolve as he

    orig = dict(he.PROPOSAL_PRIORITY)
    try:
        # memory_extract_consolidate: 3 applied → EMA 0.89 (提权)
        # sandbox_worker_pool: 3 rejected → EMA 0.11 (降权)
        proposals = [
            {"id": "a1", "kind": "structural", "pattern": "memory_extract_consolidate", "status": "applied", "ts": "2026-08-01 10:00:00"},
            {"id": "a2", "kind": "structural", "pattern": "memory_extract_consolidate", "status": "applied", "ts": "2026-08-02 10:00:00"},
            {"id": "a3", "kind": "structural", "pattern": "memory_extract_consolidate", "status": "applied", "ts": "2026-08-03 10:00:00"},
            {"id": "b1", "kind": "param", "pattern": "sandbox_worker_pool", "status": "rejected", "ts": "2026-08-01 10:00:00"},
            {"id": "b2", "kind": "param", "pattern": "sandbox_worker_pool", "status": "rejected", "ts": "2026-08-02 10:00:00"},
            {"id": "b3", "kind": "param", "pattern": "sandbox_worker_pool", "status": "rejected", "ts": "2026-08-03 10:00:00"},
        ]
        # 重置为中性权重后跑 meta 逻辑
        he.PROPOSAL_PRIORITY["memory_extract_consolidate"] = 1.0
        he.PROPOSAL_PRIORITY["sandbox_worker_pool"] = 1.0
        stats = he.meta_analyze(proposals)
        # 模拟 cmd_meta 的反馈循环
        for k, v in stats["by_pattern"].items():
            if v["pass_rate"] >= 0.8 and k in he.PROPOSAL_PRIORITY:
                he.PROPOSAL_PRIORITY[k] = min(he.PROPOSAL_PRIORITY[k] * 1.2, 1.5)
            elif v["pass_rate"] <= 0.3 and k in he.PROPOSAL_PRIORITY:
                he.PROPOSAL_PRIORITY[k] = max(he.PROPOSAL_PRIORITY[k] * 0.7, 0.3)
        assert he.PROPOSAL_PRIORITY["memory_extract_consolidate"] == 1.2  # 提权
        assert he.PROPOSAL_PRIORITY["sandbox_worker_pool"] == 0.7  # 降权
    finally:
        he.PROPOSAL_PRIORITY = orig


def test_auto_propose_meta_weight_blocks_low_pass(tmp_path, monkeypatch):
    """元层接线: pattern 历史通过率 ≤30% (n≥3) → 该 pattern 候选被否决"""
    from scripts import harness_evolve as he

    (tmp_path / "data").mkdir(exist_ok=True)
    prop_file = tmp_path / "data" / "harness_proposals.jsonl"
    monkeypatch.setattr(he, "PROPOSALS", prop_file)
    # reactive_compaction 3 提案全 rejected → 通过率 0.0 (触发元层否决)
    for pid in ["x1", "x2", "x3"]:
        prop_file.open("a").write(json.dumps({
            "id": pid, "kind": "param", "pattern": "reactive_compaction", "status": "rejected",
        }) + "\n")

    metrics = [  # low_citation → context_budget_up (reactive_compaction) / sim_threshold_strict
        {"query": "知识缺口问题", "citations": 0, "success": True, "error": None, "ms": 100},
        {"query": "知识缺口问题", "citations": 0, "success": True, "error": None, "ms": 100},
        {"query": "知识缺口问题", "citations": 0, "success": True, "error": None, "ms": 100},
    ]
    created = he.auto_propose(metrics=metrics, top_k=3)
    ids = {c["id"] for c in created}
    # context_budget_up (reactive_compaction, rate=0.0) 被否决;
    # sim_threshold_strict (field_level_source_grounding, 无样本) 中性 0.5 保留
    assert "context_budget_up" not in ids
    assert "sim_threshold_strict" in ids
    assert all(c.get("meta_weight", 0) > 0 for c in created)


def test_verify_answer_detects_signals():
    """postgen_verify: 引用一致性 / 自洽性 / 短回答检测"""
    from scripts import compliance_qa as qa

    chunks = [
        {"doc": "算法备案管理办法.md", "title": "备案流程"},
        {"doc": "生成式AI服务规定.md", "title": "总则"},
    ]
    # 一致: 引用均在检索块内 → 无信号
    ok = qa._verify_answer(
        "根据[文档: 算法备案管理办法.md | 章节: 备案流程], 需提交安全评估材料。\n\n引用来源:\n- 算法备案管理办法.md",
        chunks)
    assert ok["inconsistent_count"] == 0
    assert ok["contradiction"] is False
    # 虚构引用: 引用不在检索块 → inconsistent_citation
    bad = qa._verify_answer(
        "据[文档: 不存在的法规.md | 章节: x]规定...\n\n引用来源:\n- 不存在的法规.md", chunks)
    assert bad["inconsistent_count"] == 1
    assert "不存在的法规.md" in bad["inconsistent"]
    # 自洽矛盾: 声称未找到却带引用
    contra = qa._verify_answer(
        "资料中未找到相关内容。\n\n引用来源:\n- 算法备案管理办法.md", chunks)
    assert contra["contradiction"] is True
    # 短回答: <100 字符且无引用
    short = qa._verify_answer("不清楚。", chunks)
    assert short["short_answer"] is True


def test_run_regression_collects_verify_signal(monkeypatch):
    """run_regression: VERIFY_STATS 增量 → 结果 verify 字段 → summarize 汇总"""
    from scripts import compliance_qa as qa_mod
    from scripts import harness_evolve as he

    long_ok = "详细回答。" + "内容。" * 120 + "[文档: 算法备案管理办法.md | 章节: 备案流程]\n\n引用来源:\n- 算法备案管理办法.md"

    def fake_compile_context(q, top_k=3, mask_metadata=False):
        return [{"doc": "算法备案管理办法.md", "title": "备案流程", "hits": 0.8, "char_len": 300}]

    def fake_answer(q, top_k=3):
        qa_mod.VERIFY_STATS["checked"] += 1
        qa_mod.VERIFY_STATS["inconsistent_citation"] += 1  # 模拟检测到 1 个不一致
        qa_mod.CACHE_STATS["hit"] += 1  # 模拟缓存命中
        qa_mod.GUARD_STATS["intent"] += 1  # 模拟守卫命中
        return long_ok

    monkeypatch.setattr(qa_mod, "compile_context", fake_compile_context)
    monkeypatch.setattr(qa_mod, "answer", fake_answer)
    results = he.run_regression(["测试问题"], top_k=3)
    assert results[0]["verify"]["checked"] == 1
    assert results[0]["verify"]["inconsistent_citation"] == 1
    assert results[0]["cache"]["hit"] == 1
    assert results[0]["guards"]["intent"] == 1
    s = he.summarize(results)
    assert s["verify_inconsistent"] == 1
    assert s["cache_hit_rate"] == 1.0
    assert s["guards_hit"] == 1
    assert s["citation_rate"] == 1.0


def test_run_regression_collects_consolidate_signal(monkeypatch):
    """P1-B: run_regression 采集 CONSOLIDATE_STATS 增量 → summarize.consolidate_actions"""
    from scripts import compliance_qa as qa_mod
    from scripts import harness_evolve as he

    long_ok = "详细回答。" + "内容。" * 120 + "[文档: 算法备案管理办法.md | 章节: 备案流程]\n\n引用来源:\n- 算法备案管理办法.md"

    def fake_compile_context(q, top_k=3, mask_metadata=False):
        return [{"doc": "算法备案管理办法.md", "title": "备案流程", "hits": 0.8, "char_len": 300}]

    def fake_answer(q, top_k=3):
        qa_mod.CONSOLIDATE_STATS["runs"] += 1  # 模拟钩子执行
        qa_mod.CONSOLIDATE_STATS["consolidated"] += 1  # 模拟合并 1 条
        qa_mod.CONSOLIDATE_STATS["filtered"] += 2  # 模拟过滤 2 条
        return long_ok

    monkeypatch.setattr(qa_mod, "compile_context", fake_compile_context)
    monkeypatch.setattr(qa_mod, "answer", fake_answer)
    results = he.run_regression(["测试问题"], top_k=3)
    assert results[0]["consolidate"]["runs"] == 1
    assert results[0]["consolidate"]["consolidated"] == 1
    assert results[0]["consolidate"]["filtered"] == 2
    s = he.summarize(results)
    assert s["consolidate_runs"] == 1
    assert s["consolidate_actions"] == 3


def test_memory_consolidate_merges_similar(monkeypatch, tmp_path):
    """P1-B: 记忆巩固合并相似 query (保留引用更高者), 文件原子写回"""
    from scripts import compliance_qa as qa

    cache_file = tmp_path / "qa_memory_cache.jsonl"
    cache_file.write_text("\n".join([
        json.dumps({"query": "算法备案需要什么材料", "answer": "A" * 300, "citations": 5, "ts": "2026-08-10 10:00:00"}),
        json.dumps({"query": "算法备案需要哪些材料", "answer": "B" * 300, "citations": 2, "ts": "2026-08-09 10:00:00"}),
        json.dumps({"query": "数据跨境传输合规要求", "answer": "C" * 300, "citations": 3, "ts": "2026-08-10 10:00:00"}),
    ]) + "\n")
    monkeypatch.setattr(qa, "MEMORY_CACHE_PATH", cache_file)
    qa._memory_cache.clear()

    result = qa._memory_consolidate()
    assert result["consolidated"] == 1  # 前两条相似 → 合并 1
    assert result["filtered"] == 0
    # 保留引用更高者 (citations=5 的"算法备案需要什么材料")
    assert "算法备案需要什么材料" in qa._memory_cache
    assert "算法备案需要哪些材料" not in qa._memory_cache
    assert "数据跨境传输合规要求" in qa._memory_cache
    # 文件已原子重写 (不含被合并条目)
    disk = cache_file.read_text()
    assert "算法备案需要哪些材料" not in disk
    assert "算法备案需要什么材料" in disk
    qa._memory_cache.clear()


def test_memory_consolidate_filters_stale_low_value(monkeypatch, tmp_path):
    """P1-B: 陈旧低引用条目 (cit<2 且 >30天) 淘汰; 新低引用保留"""
    from scripts import compliance_qa as qa

    cache_file = tmp_path / "qa_memory_cache.jsonl"
    old = (time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - 40 * 86400)))
    fresh = time.strftime("%Y-%m-%d %H:%M:%S")
    cache_file.write_text("\n".join([
        json.dumps({"query": "旧的低价值条目", "answer": "A" * 300, "citations": 1, "ts": old}),
        json.dumps({"query": "新的低价值条目", "answer": "B" * 300, "citations": 1, "ts": fresh}),
        json.dumps({"query": "高引用条目", "answer": "C" * 300, "citations": 6, "ts": old}),
    ]) + "\n")
    monkeypatch.setattr(qa, "MEMORY_CACHE_PATH", cache_file)
    qa._memory_cache.clear()

    result = qa._memory_consolidate()
    assert result["filtered"] == 1  # 仅旧+低引用淘汰
    assert "旧的低价值条目" not in qa._memory_cache
    assert "新的低价值条目" in qa._memory_cache  # 新条目即使低引用也保留
    assert "高引用条目" in qa._memory_cache
    qa._memory_cache.clear()


def test_query_similar_guards():
    """P1-B: 相似判定 — 同主题变体相似, 不同主题/长度比超限不相似"""
    from scripts import compliance_qa as qa

    assert qa._query_similar("算法备案需要什么材料", "算法备案需要哪些材料") is True
    assert qa._query_similar("算法备案要求", "算法备案的要求是什么") is True  # 子串包含
    assert qa._query_similar("算法备案要求", "数据跨境传输合规") is False  # 不同主题
    assert qa._query_similar("算法备案", "算法备案管理办法全文以及实施细则解读与常见问题解答汇总") is False  # 长度比超限


def test_memory_consolidate_off_switch():
    """P1-B: CONSOLIDATE_ENABLED 落地后生产默认 True; impl_marker 在源码"""
    from scripts import compliance_qa as qa

    assert qa.CONSOLIDATE_ENABLED is True  # 已 apply (evaluate passed)
    src = Path(qa.__file__).read_text(encoding="utf-8")
    assert "CONSOLIDATE_ENABLED: bool = True" in src  # impl_marker 存在于源码 (evaluate 判定)


def test_writeback_status_keeps_applied():
    """账本状态保持: 已落地 (applied) 提案重跑 evaluate 通过 → 保持 applied (不被打回 passed)"""
    from scripts import harness_evolve as he

    # applied + 通过 → 保持 applied
    p = {"id": "x", "status": "applied"}
    assert he._writeback_status(p, True) == "applied"
    assert p["status"] == "applied"
    # applied + 失败 → rejected (落地失效? 不 — 仅状态记录, 代码已落地; 但账本如实记录重跑失败)
    p2 = {"id": "y", "status": "applied"}
    assert he._writeback_status(p2, False) == "rejected"
    assert p2["status"] == "rejected"
    # passed + 通过 → passed
    p3 = {"id": "z", "status": "passed"}
    assert he._writeback_status(p3, True) == "passed"
    assert p3["status"] == "passed"

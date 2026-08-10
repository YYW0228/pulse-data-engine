"""harness_evolve 共进化闭环测试 — scan/propose/worst_questions 逻辑"""

from __future__ import annotations

import json
import sys
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
    """元层统计: 提案通过率特征"""
    from scripts import harness_evolve as he

    proposals = [
        {"id": "a", "kind": "param", "pattern": "reactive_compaction", "status": "applied"},
        {"id": "b", "kind": "param", "pattern": "reactive_compaction", "status": "rejected"},
        {"id": "c", "kind": "structural", "pattern": "memory_extract_consolidate", "status": "applied"},
        {"id": "d", "kind": "structural", "pattern": "middleware_chain", "status": "applied"},
    ]
    stats = he.meta_analyze(proposals)
    assert stats["total"] == 4
    assert stats["applied"] == 3
    assert stats["rejected"] == 1
    # param 50% vs structural 100%
    assert stats["by_kind"]["param"]["pass_rate"] == 0.5
    assert stats["by_kind"]["structural"]["pass_rate"] == 1.0
    # pattern 级
    assert stats["by_pattern"]["memory_extract_consolidate"]["pass_rate"] == 1.0
    assert stats["by_pattern"]["reactive_compaction"]["pass_rate"] == 0.5


def test_meta_updates_priority():
    """元层反馈: 高通过率提权 / 低通过率降权"""
    from scripts import harness_evolve as he

    orig = dict(he.PROPOSAL_PRIORITY)
    try:
        proposals = [
            {"id": "a", "kind": "structural", "pattern": "memory_extract_consolidate", "status": "applied"},
            {"id": "b", "kind": "structural", "pattern": "middleware_chain", "status": "applied"},
            {"id": "c", "kind": "param", "pattern": "sandbox_worker_pool", "status": "rejected"},
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

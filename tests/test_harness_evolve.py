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
    monkeypatch.chdir(tmp_path)

    # 构造 data 目录
    (tmp_path / "data").mkdir(exist_ok=True)
    rc = he.cmd_propose(type("A", (), {"n": 5})())
    assert rc == 0
    proposals = (tmp_path / "data" / "harness_proposals.jsonl").read_text().splitlines()
    assert len(proposals) == 1
    p = json.loads(proposals[0])
    assert "regression_set" in p
    assert p["threshold"]["min_citations"] == 1

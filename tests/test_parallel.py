"""parallel 最小并行子任务测试 — 路由/合并/隔离逻辑 (不依赖真实网络)"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest


def test_is_complex_query():
    from scripts.parallel import is_complex_query

    assert is_complex_query("中国 AI 公司出海欧盟, 数据跨境要求")  # 跨域
    assert is_complex_query("中欧标识要求有何不同")  # 对比
    assert not is_complex_query("算法备案的要求是什么")  # 简单
    assert not is_complex_query("深度合成内容需要标识吗")  # 简单


def test_should_parallel_customer_db():
    from scripts.parallel import should_parallel

    # 客户库激活 → 总是并行 (双库隔离)
    assert should_parallel("简单问题", customer_db="acme.duckdb") is True
    # 无客户库 + 简单 → 串行薄路径
    assert should_parallel("算法备案要求", customer_db=None) is False


def test_retrieve_global_returns_rows():
    """全局库检索 (真实库, 只验证函数契约) — 需 embedding 模型"""
    pytest.importorskip("sentence_transformers", reason="需要 ml 组依赖")
    from scripts.parallel import _global_db, _retrieve_global

    rows = _retrieve_global("算法备案", 3, _global_db())
    assert isinstance(rows, list)
    if rows:
        r = rows[0]
        assert "doc" in r and "content" in r and "hits" in r
        assert r["source"] == "global"


def test_retrieve_customer_missing_db():
    from scripts.parallel import _retrieve_customer

    assert _retrieve_customer("测试", 3, "/nonexistent/x.duckdb") == []


def test_merge_sorts_by_sim(monkeypatch):
    """合并逻辑: 跨源统一按 sim 排序"""
    from scripts import parallel as par

    # mock 子任务返回
    calls = {}

    def fake_subprocess(kind, query, top_k, db_path):
        calls[kind] = True
        if kind == "global":
            return [{"doc": "g.md", "title": "g", "content": "x", "hits": 0.5,
                     "char_len": 10, "importance": 0.3, "source": "global"}]
        return [{"doc": "c.md", "title": "c", "content": "y", "hits": 0.9,
                 "char_len": 10, "importance": 0.3, "source": "customer"}]

    monkeypatch.setattr(par, "_subprocess_retrieve", fake_subprocess)
    h = par.parallel_retrieve("测试", top_k=3, customer_db="fake.duckdb")
    assert h["per_source"] == {"global_kb": 1, "customer_kb": 1}
    # 排序: customer (0.9) 应在 global (0.5) 前
    assert h["chunks"][0]["doc"] == "c.md"
    assert h["chunks"][0]["src"] == "customer_kb"
    assert "total_ms" in h

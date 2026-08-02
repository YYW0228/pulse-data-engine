"""pulse/vector_store.py 测试 — 抽象层接口验证"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_duckdb_store_upsert_and_count(tmp_path):
    from pulse.vector_store import DuckDBStore

    store = DuckDBStore(tmp_path / "v.duckdb")
    chunks = [
        {"doc_name": "a.md", "title": "节1", "content": "内容一内容一内容一内容一", "importance": 0.8},
        {"doc_name": "a.md", "title": "节2", "content": "内容二内容二内容二内容二", "importance": 0.5},
    ]
    n = store.upsert_chunks(chunks, [[0.1] * 512, [0.2] * 512])
    assert n == 2
    assert store.count() == 2
    store.close()


def test_duckdb_store_incremental_replace(tmp_path):
    """增量替换: 同 doc_name 重插不残留旧块"""
    from pulse.vector_store import DuckDBStore

    store = DuckDBStore(tmp_path / "v.duckdb")
    store.upsert_chunks(
        [{"doc_name": "a.md", "title": "节1", "content": "内容一内容一内容一内容一"}],
        [[0.1] * 512],
    )
    # 同一文档重新 upsert (2 块)
    store.upsert_chunks(
        [
            {"doc_name": "a.md", "title": "节1", "content": "新内容一"},
            {"doc_name": "a.md", "title": "节2", "content": "新内容二"},
        ],
        [[0.1] * 512, [0.2] * 512],
    )
    assert store.count() == 2  # 2 块 (旧 1 块被替换, 不残留)
    store.close()


def test_duckdb_store_search_filters(tmp_path):
    from pulse.vector_store import DuckDBStore

    store = DuckDBStore(tmp_path / "v.duckdb")
    store.upsert_chunks(
        [
            {"doc_name": "a.md", "title": "节1", "content": "内容一内容一内容一内容一"},
            {"doc_name": "b.md", "title": "节1", "content": "内容二内容二内容二内容二"},
        ],
        [[0.1] * 512, [0.9] * 512],
    )
    r = store.search([0.1] * 512, top_k=5, filters={"doc_name": "a.md"})
    assert len(r) == 1
    assert r[0]["doc_name"] == "a.md"
    store.close()


def test_duckdb_store_delete(tmp_path):
    from pulse.vector_store import DuckDBStore

    store = DuckDBStore(tmp_path / "v.duckdb")
    store.upsert_chunks(
        [{"doc_name": "a.md", "title": "节1", "content": "内容一内容一内容一内容一"}],
        [[0.1] * 512],
    )
    assert store.delete_doc("_nonexistent_") == 0  # 不存在 → 0
    store.close()


def test_get_store_factory():
    """工厂默认返回 DuckDB"""
    from pulse.vector_store import DuckDBStore, get_store

    store = get_store("duckdb")
    assert isinstance(store, DuckDBStore)
    store.close()

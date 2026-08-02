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


def test_duckdb_store_empty_search(tmp_path):
    """边界: 空库搜索返回空列表 (不崩溃)"""
    from pulse.vector_store import DuckDBStore

    store = DuckDBStore(tmp_path / "v.duckdb")
    r = store.search([0.1] * 512, top_k=5)
    assert r == []
    # 空库 delete 也安全
    assert store.delete_doc("anything.md") == 0
    store.close()


def test_duckdb_store_bulk_upsert(tmp_path):
    """边界: 大批量 upsert (200 块) 性能与计数正确"""
    from pulse.vector_store import DuckDBStore

    store = DuckDBStore(tmp_path / "v.duckdb")
    chunks = [
        {"doc_name": f"doc_{i % 10}.md", "title": f"节{j}",
         "content": f"内容{i}-{j}内容内容内容内容内容", "importance": 0.5 + (i % 5) * 0.1}
        for i in range(200) for j in range(20)
    ]
    embeddings = [[round((i + j) / 1000, 6)] * 512 for i in range(200) for j in range(20)]
    n = store.upsert_chunks(chunks, embeddings)
    assert n == 4000
    assert store.count() == 4000
    # 部分替换: 只重新 upsert doc_0 的块 (i%10==0 → 400 块) → 其余 doc 保留
    doc0_chunks = [c for c in chunks if c["doc_name"] == "doc_0.md"]
    assert len(doc0_chunks) == 400
    store.upsert_chunks(doc0_chunks, [[0.5] * 512] * 400)
    assert store.count() == 4000  # doc_0 替换, doc_1..9 保留, 总量不变
    store.close()


def test_duckdb_store_complex_filter(tmp_path):
    """边界: 复杂过滤 (doc_name + title 组合)"""
    from pulse.vector_store import DuckDBStore

    store = DuckDBStore(tmp_path / "v.duckdb")
    store.upsert_chunks(
        [
            {"doc_name": "a.md", "title": "节1", "content": "内容一内容一内容一内容一"},
            {"doc_name": "a.md", "title": "节2", "content": "内容二内容二内容二内容二"},
            {"doc_name": "b.md", "title": "节1", "content": "内容三内容三内容三内容三"},
        ],
        [[0.1] * 512, [0.2] * 512, [0.3] * 512],
    )
    # doc_name + title 双条件
    r = store.search([0.1] * 512, top_k=5, filters={"doc_name": "a.md", "title": "节1"})
    assert len(r) == 1
    assert r[0]["title"] == "节1"
    store.close()

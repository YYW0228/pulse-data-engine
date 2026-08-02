"""
pulse/vector_store.py — 向量存储抽象层 (适配器模式)

统一接口: 换后端 (DuckDB VSS / Qdrant / 未来) 零改动上层。
对应"数据适配流水线"方法 D: 换数据源/换向量库不碰框架层。

设计:
  VectorStore (ABC):
    upsert_chunks(chunks)   — 增量替换 (同 doc_name 先删后插)
    search(query_vec, top_k, filters) — 向量检索 + Payload 过滤
    count() / delete_doc(doc_name) / close()

实现:
  DuckDBStore — 当前生产 (零成本, 246 块规模够用)
  QdrantStore  — 客户规模后端 (代码就位, 容器化交付时启用)

用法 (上层 compliance_qa 只依赖 ABC):
  store = get_store("duckdb")   # 或 "qdrant" (需 QDRANT_URL)
  chunks = store.search(qvec, top_k=3, filters={"doc_name": "xx"})
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class VectorStore(ABC):
    """向量存储统一接口"""

    @abstractmethod
    def upsert_chunks(self, chunks: list[dict], embeddings: list[list[float]]) -> int:
        """增量替换: 同 doc_name 先删后插, 返回写入块数"""

    @abstractmethod
    def search(self, query_vec: list[float], top_k: int = 5,
               filters: dict[str, Any] | None = None) -> list[dict]:
        """向量检索 + 过滤, 返回 [{doc_name, title, content, hits, importance}]"""

    @abstractmethod
    def delete_doc(self, doc_name: str) -> int:
        """删除某文档全部块 (数据替换零残留)"""

    @abstractmethod
    def count(self) -> int:
        """总块数"""

    @abstractmethod
    def close(self) -> None:
        pass


# ── DuckDB 实现 (当前生产) ────────────────────────────────────────────

class DuckDBStore(VectorStore):
    """DuckDB VSS 后端 — 零成本, 单机, 246 块规模最优"""

    def __init__(self, db_path: str | Path = "data/compliance.duckdb"):
        import duckdb

        self._path = str(db_path)
        self._con = duckdb.connect(self._path)
        # 扩展目录兜底 (systemd/CI 环境 HOME 可能异常)
        ext_dir = Path.home() / ".duckdb" / "extensions"
        if ext_dir.exists():
            self._con.execute(f"SET extension_directory='{ext_dir}'")
        self._con.execute("INSTALL vss")
        self._con.execute("LOAD vss")
        self._con.execute("SET hnsw_enable_experimental_persistence = true")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._con.execute("""
            CREATE TABLE IF NOT EXISTS compliance_chunks (
                doc_id INTEGER, doc_name VARCHAR, title VARCHAR, content VARCHAR,
                char_len INTEGER, embedding FLOAT[512], importance FLOAT,
                content_hash VARCHAR, last_access TIMESTAMP
            )
        """)

    def upsert_chunks(self, chunks: list[dict], embeddings: list[list[float]]) -> int:
        for c, vec in zip(chunks, embeddings):
            self._con.execute("DELETE FROM compliance_chunks WHERE doc_name=?", [c["doc_name"]])
        for c, vec in zip(chunks, embeddings):
            self._con.execute(
                "INSERT INTO compliance_chunks VALUES (?,?,?,?,?,?,?,?,now())",
                [c.get("doc_id", 0), c["doc_name"], c["title"], c["content"],
                 len(c["content"]), vec, c.get("importance", 0.5), c.get("content_hash", "")],
            )
        return len(chunks)

    def search(self, query_vec: list[float], top_k: int = 5,
               filters: dict[str, Any] | None = None) -> list[dict]:
        sql = """
            SELECT doc_name, title, content, char_len, importance,
                   list_cosine_similarity(embedding, ?) as sim
            FROM compliance_chunks
        """
        params: list[Any] = [query_vec]
        if filters:
            conds = []
            for k, v in filters.items():
                if k in ("doc_name", "title"):
                    conds.append(f"{k} = ?")
                    params.append(v)
            if conds:
                sql += " WHERE " + " AND ".join(conds)
        sql += " ORDER BY sim DESC LIMIT ?"
        params.append(top_k)
        rows = self._con.execute(sql, params).fetchall()
        return [
            {"doc_name": r[0], "title": r[1], "content": r[2],
             "char_len": r[3], "importance": r[4], "hits": r[5]}
            for r in rows
        ]

    def delete_doc(self, doc_name: str) -> int:
        cur = self._con.execute("DELETE FROM compliance_chunks WHERE doc_name=?", [doc_name])
        row = cur.fetchone()
        return row[0] if row else 0

    def count(self) -> int:
        return self._con.execute("SELECT COUNT(*) FROM compliance_chunks").fetchone()[0]

    def close(self) -> None:
        self._con.close()


# ── Qdrant 实现 (客户规模, 容器化交付时启用) ─────────────────────────

class QdrantStore(VectorStore):
    """Qdrant 后端 — 多租户/10万+块/混合检索

    启用条件:
      - QDRANT_URL 环境变量 (默认 http://localhost:6333)
      - 需安装 qdrant-client: uv pip install qdrant-client
    代码就位不启用 (Rule of Three: 无真实客户规模前不切换)
    """

    COLLECTION = "compliance_chunks"

    def __init__(self, url: str | None = None, api_key: str | None = None):
        try:
            from qdrant_client import QdrantClient
        except ImportError:
            raise RuntimeError("qdrant-client 未安装: uv pip install qdrant-client") from None
        self._client = QdrantClient(
            url=url or os.environ.get("QDRANT_URL", "http://localhost:6333"),
            api_key=api_key or os.environ.get("QDRANT_API_KEY"),
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        if not self._client.collection_exists(self.COLLECTION):
            self._client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=512, distance=Distance.COSINE),
            )

    def upsert_chunks(self, chunks: list[dict], embeddings: list[list[float]]) -> int:
        from qdrant_client.models import PointStruct

        # 增量替换: 先删同 doc_name (零残留)
        doc_names = {c["doc_name"] for c in chunks}
        for dn in doc_names:
            self.delete_doc(dn)

        points = []
        for i, (c, vec) in enumerate(zip(chunks, embeddings)):
            points.append(PointStruct(
                id=i,
                vector=vec,
                payload={
                    "doc_name": c["doc_name"],
                    "title": c["title"],
                    "content": c["content"],
                    "importance": c.get("importance", 0.5),
                    "char_len": len(c["content"]),
                },
            ))
        self._client.upsert(collection_name=self.COLLECTION, points=points)
        return len(points)

    def search(self, query_vec: list[float], top_k: int = 5,
               filters: dict[str, Any] | None = None) -> list[dict]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = None
        if filters:
            conditions = [
                FieldCondition(key=k, match=MatchValue(value=v))
                for k, v in filters.items() if k in ("doc_name", "title")
            ]
            if conditions:
                query_filter = Filter(must=conditions)
        hits = self._client.search(
            collection_name=self.COLLECTION,
            query_vector=query_vec,
            limit=top_k,
            query_filter=query_filter,
        )
        return [
            {"doc_name": h.payload.get("doc_name", ""), "title": h.payload.get("title", ""),
             "content": h.payload.get("content", ""), "char_len": h.payload.get("char_len", 0),
             "importance": h.payload.get("importance", 0.5), "hits": h.score}
            for h in hits
        ]

    def delete_doc(self, doc_name: str) -> int:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        res = self._client.delete(
            collection_name=self.COLLECTION,
            points_selector=Filter(
                must=[FieldCondition(key="doc_name", match=MatchValue(value=doc_name))]
            ),
        )
        return res.status  # 0=ok (Qdrant delete 返回 UpdateStatus)

    def count(self) -> int:
        return self._client.count(collection_name=self.COLLECTION).count

    def close(self) -> None:
        pass  # qdrant-client 无显式 close


# ── 工厂 ──────────────────────────────────────────────────────────────

def get_store(backend: str = "duckdb", **kwargs: Any) -> VectorStore:
    """工厂: duckdb (默认生产) / qdrant (客户规模)"""
    if backend == "qdrant":
        return QdrantStore(**kwargs)
    return DuckDBStore(**kwargs)


if __name__ == "__main__":
    # 验证 DuckDB 实现 (生产)
    store = get_store("duckdb")
    print(f"DuckDBStore 块数: {store.count()}")
    # 测试过滤查询
    r = store.search([0.1] * 512, top_k=2, filters={"doc_name": "ai-governance-core.md"})
    print(f"过滤查询: {len(r)} 条 (doc_name 过滤生效)")
    store.close()

"""parallel — 最小并行/子任务抽象 (优先级 B)

设计 (局部简化 + 全局复杂化):
  - 简单查询: 原路径 (薄, 单线程检索)
  - 复杂查询 (跨域/多源): fork 2-3 个隔离子任务 (ThreadPool + 独立 DuckDB 连接)
    → 每个子任务返回结构化 handoff (摘要 + 引用 + 置信度)
    → 主循环最终合成 + 护栏

子任务类型:
  1. global_kb: 全局法规库检索
  2. customer_kb: acme 客户库检索 (若激活)
  3. web_sources: 外部多源搜索 (dap search_engines, 零 LLM)

用法:
  from scripts.parallel import parallel_retrieve
  chunks = parallel_retrieve(query, top_k=3)

评估 (复用 harness_evolve A/B 框架):
  evaluate --proposal parallel_retrieve → 对比 耗时/引用覆盖
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 跨域/复杂意图关键词 (触发并行路径)
COMPLEX_HINTS = [
    "跨境", "出海", "欧盟", "美国", "多国", "不同", "区别", "对比",
    "同时", "以及", "和", "与", "境外", "海外", "国际",
]


def is_complex_query(query: str) -> bool:
    """简单 vs 复杂判定: 含跨域/对比关键词 → 复杂 (走并行)"""
    q = query.lower()
    return any(k in q for k in COMPLEX_HINTS)


def _retrieve_global(query: str, top_k: int, db_path: str) -> list[dict]:
    """子任务 1: 全局库检索 (独立连接)"""
    from pathlib import Path

    import duckdb

    # 复用 compliance_qa 的检索逻辑, 但用独立连接 (隔离)
    from scripts.compliance_qa import get_model

    model = get_model()
    qvec = model.encode(query, normalize_embeddings=True)
    con = duckdb.connect(db_path, read_only=True)
    try:
        ext_dir = Path.home() / ".duckdb" / "extensions"
        if ext_dir.exists():
            con.execute(f"SET extension_directory='{ext_dir}'")
        con.execute("INSTALL vss")
        con.execute("LOAD vss")
        con.execute("SET hnsw_enable_experimental_persistence = true")
        rows = con.execute(
            """
            SELECT doc_name, title, content, char_len,
                   list_cosine_similarity(embedding, ?) as sim, importance
            FROM compliance_chunks
            ORDER BY sim DESC LIMIT ?
            """,
            [qvec.tolist(), top_k * 3],
        ).fetchall()
        return [
            {"doc": d, "title": t, "content": c[:3000], "hits": round(float(s), 3),
             "char_len": cl, "importance": float(imp or 0.3), "source": "global"}
            for d, t, c, cl, s, imp in rows
        ]
    finally:
        con.close()


def _retrieve_customer(query: str, top_k: int, db_path: str) -> list[dict]:
    """子任务 2: 客户库检索 (独立连接, 隔离)"""
    from pathlib import Path

    import duckdb

    from scripts.compliance_qa import get_model

    if not Path(db_path).exists():
        return []
    model = get_model()
    qvec = model.encode(query, normalize_embeddings=True)
    con = duckdb.connect(db_path, read_only=True)
    try:
        ext_dir = Path.home() / ".duckdb" / "extensions"
        if ext_dir.exists():
            con.execute(f"SET extension_directory='{ext_dir}'")
        con.execute("INSTALL vss")
        con.execute("LOAD vss")
        rows = con.execute(
            """
            SELECT doc_name, title, content, char_len,
                   list_cosine_similarity(embedding, ?) as sim, importance
            FROM compliance_chunks
            ORDER BY sim DESC LIMIT ?
            """,
            [qvec.tolist(), top_k],
        ).fetchall()
        return [
            {"doc": d, "title": t, "content": c[:3000], "hits": round(float(s), 3),
             "char_len": cl, "importance": float(imp or 0.3), "source": "customer"}
            for d, t, c, cl, s, imp in rows
        ]
    finally:
        con.close()


def _search_web(query: str, top_k: int) -> list[dict]:
    """子任务 3: 外部多源搜索 (零 LLM, 失败静默)"""
    try:
        import sys
        from pathlib import Path

        dap_root = Path.home() / "projects" / "data-acquisition-pipeline"
        if str(dap_root / "src") not in sys.path:
            sys.path.insert(0, str(dap_root / "src"))
        from dap.adapters.search_engines import search_all

        results = search_all(query, num=top_k, engines=["baidu"])
        return [
            {"doc": f"web:{r.get('source', 'web')}", "title": r.get("title", "")[:60],
             "content": r.get("snippet", "")[:1000], "hits": 0.5,
             "char_len": min(len(r.get("snippet", "")), 1000), "importance": 0.3,
             "source": "web", "url": r.get("url", "")}
            for r in results[:top_k]
        ]
    except Exception:
        return []


def _subprocess_retrieve(kind: str, query: str, top_k: int, db_path: str) -> list[dict]:
    """子任务进程隔离执行 — 避免 ThreadPool + duckdb HNSW 线程竞争 (macOS 实测崩溃)

    参数用 base64 传递 (避免引号/中文转义问题)
    """
    import base64
    import subprocess
    import sys as _sys

    payload = base64.b64encode(json.dumps(
        {"kind": kind, "query": query, "top_k": top_k, "db_path": db_path}
    ).encode()).decode()
    code = (
        "import sys, json, base64; sys.path.insert(0, '.'); "
        "from scripts.parallel import _retrieve_global, _retrieve_customer; "
        "p = json.loads(base64.b64decode(sys.argv[1]).decode()); "
        "fn = _retrieve_global if p['kind'] == 'global' else _retrieve_customer; "
        "r = fn(p['query'], p['top_k'], p['db_path']); "
        "print(json.dumps(r, ensure_ascii=False))"
    )
    try:
        proc = subprocess.run(
            [_sys.executable, "-c", code, payload],
            capture_output=True, text=True, timeout=60,
            cwd=str(Path(__file__).resolve().parent.parent),
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return json.loads(proc.stdout.strip())
    except Exception:
        pass
    return []


def parallel_retrieve(query: str, top_k: int = 3, customer_db: str | None = None) -> dict:
    """并行检索 (进程隔离): 全局 + 客户(可选) → 合并 handoff

    返回结构化 handoff (不返回原始长上下文):
      {chunks, sources, total_ms, per_source}
    """
    import sys as _sys

    t0 = time.time()
    tasks: list[tuple[str, object]] = [
        ("global_kb", lambda: _subprocess_retrieve("global", query, top_k, _global_db()))
    ]
    if customer_db:
        tasks.append(("customer_kb", lambda: _subprocess_retrieve("customer", query, top_k, customer_db)))

    results: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max(2, len(tasks))) as ex:
        futures = {ex.submit(fn): name for name, fn in tasks}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                results[name] = fut.result()
            except Exception as e:
                errors[name] = str(e)[:100]
                results[name] = []

    if errors:
        print(f"[parallel] 子任务异常: {errors}", file=_sys.stderr)

    # 合并 + 排序 (跨源统一按 sim)
    merged: list[dict] = []
    for src, chunks in results.items():
        for c in chunks:
            c["src"] = src
            merged.append(c)
    merged.sort(key=lambda x: -x.get("hits", 0))

    # 结构化 handoff: 每源最多 top_k, 总合并不超过 top_k * 2
    handoff = {
        "chunks": merged[: top_k * 2],
        "sources": list(results.keys()),
        "per_source": {k: len(v) for k, v in results.items()},
        "total_ms": round((time.time() - t0) * 1000, 1),
    }
    return handoff


def _global_db() -> str:
    from pathlib import Path
    return str(Path(__file__).resolve().parent.parent / "data" / "compliance.duckdb")


def should_parallel(query: str, customer_db: str | None = None) -> bool:
    """是否走并行路径: 复杂查询 或 客户库激活时"""
    if customer_db:
        return True  # 双库场景总是并行 (全局+客户隔离检索)
    return is_complex_query(query)

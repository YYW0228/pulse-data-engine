"""
scripts/compliance_index.py — 合规文档索引器 v2 (向量版)

把 china-ai-governance 的 md 文档按标题分块 → DuckDB + embedding 向量
供 RAG 问答语义检索。

用法:
  uv run python -m scripts.compliance_index
  uv run python -m scripts.compliance_index --source <dir> --rebuild
"""

import argparse
import re
import time
from pathlib import Path

import duckdb

DB_PATH = Path("data/compliance.duckdb")


def split_markdown(text: str, min_chars: int = 50) -> list[dict]:
    """按 ## 标题切分 md 文档为块 + 重要性评分

    重要性评分 (0-1):
      - 标题层级: ## (0.9) > ### (0.7) > #### (0.5) > 其他 (0.3)
      - 实体密度: 含法规/条款编号 (第X条/办法/规定/指南) 加权
      - 时效性: 含年份 (2024-2026) 加权
    """
    blocks = []
    lines = text.splitlines()
    current_title = "文档头部"
    current_content: list[str] = []

    def _importance(title: str, content: str) -> float:
        score = 0.3  # 基础分
        # 标题层级
        if title.startswith("## "):
            score = 0.9
        elif title.startswith("### "):
            score = 0.7
        elif title.startswith("#### "):
            score = 0.5
        # 法规/条款实体
        if re.search(r"第[一二三四五六七八九十\d]+条|办法|规定|指南|条例|法律|办法|标准", title + content[:500]):
            score += 0.15
        # 时效性 (近3年)
        if re.search(r"20(2[4-6])", content[:1000]):
            score += 0.05
        return round(min(score, 1.0), 2)

    for line in lines:
        if line.startswith("## "):
            if len("\n".join(current_content)) >= min_chars:
                blocks.append({
                    "title": current_title,
                    "content": "\n".join(current_content).strip(),
                })
            current_title = line[3:].strip()
            current_content = [line]
        else:
            current_content.append(line)

    if len("\n".join(current_content)) >= min_chars:
        blocks.append({
            "title": current_title,
            "content": "\n".join(current_content).strip(),
        })

    # 加重要性
    for b in blocks:
        b["importance"] = _importance(b["title"], b["content"])

    return blocks


def get_embedder():
    """懒加载 embedding 模型 (首次调用才下载)"""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("BAAI/bge-small-zh-v1.5")


def index_docs(source: Path, rebuild: bool = False, include_jsonl: bool = False) -> dict:
    """索引目录下所有 md 文档 + 生成向量"""
    con = duckdb.connect(str(DB_PATH))
    # 兜底: 显式设置扩展目录 (systemd 环境 HOME 可能异常) — 必须在 LOAD 之前
    # 兜底: 显式设置扩展目录 (systemd 环境 HOME 可能异常; 本机/CI home 均可写)
    ext_dir = Path.home() / ".duckdb" / "extensions"
    if ext_dir.exists():
        con.execute(f"SET extension_directory='{ext_dir}'")
    con.execute("INSTALL vss")  # 幂等: CI 环境自动下载到 home
    con.execute("LOAD vss")
    con.execute("SET hnsw_enable_experimental_persistence = true")
    if rebuild:
        con.execute("DROP TABLE IF EXISTS compliance_chunks")
    con.execute("""
        CREATE TABLE IF NOT EXISTS compliance_chunks (
            doc_id INTEGER,
            doc_name VARCHAR,
            title VARCHAR,
            content VARCHAR,
            char_len INTEGER,
            embedding FLOAT[512],
            importance FLOAT
        )
    """)
    if rebuild:
        con.execute("DELETE FROM compliance_chunks")

    files = sorted(source.rglob("*.md"))
    # 支持 doc_parser 输出的 JSONL (客户文档: pdf/docx → 解析块)
    if include_jsonl:
        files = files + sorted(source.rglob("*.jsonl"))
    doc_id = 0
    total_chunks = 0
    total_chars = 0

    # 批量生成向量
    print("加载 embedding 模型...")
    t0 = time.time()
    model = get_embedder()

    for f in files:
        doc_id += 1
        if f.suffix == ".jsonl":
            blocks = _load_jsonl_blocks(f)
        else:
            text = f.read_text(encoding="utf-8")
            blocks = split_markdown(text)
        if not blocks:
            continue
        # 增量替换: 同 doc_name 旧块先删 (数据替换的核心语义)
        con.execute("DELETE FROM compliance_chunks WHERE doc_name=?", [f.name])
        # 批量编码该文档所有块
        contents = [b["content"] for b in blocks]
        vecs = model.encode(contents, normalize_embeddings=True)
        for b, vec in zip(blocks, vecs):
            total_chunks += 1
            total_chars += len(b["content"])
            con.execute(
                "INSERT INTO compliance_chunks VALUES (?,?,?,?,?,?,?)",
                [doc_id, f.name, b["title"], b["content"], len(b["content"]), vec.tolist(), b["importance"]],
            )

    # 建向量索引
    con.execute("""
        CREATE INDEX IF NOT EXISTS chunk_vec_idx
        ON compliance_chunks USING HNSW (embedding)
    """)

    elapsed = time.time() - t0
    con.close()
    return {"docs": doc_id, "chunks": total_chunks, "chars": total_chars, "embed_seconds": round(elapsed, 1)}


def _load_jsonl_blocks(f: Path) -> list[dict]:
    """加载 doc_parser 输出的 JSONL 块"""
    import json

    blocks = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            b = json.loads(line)
            b["doc_name"] = b.get("doc_name", f.name)
            blocks.append(b)
        except json.JSONDecodeError:
            continue
    return blocks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="/root/projects/china-ai-governance/ai-governance-legal/references",
        help="md 文档目录",
    )
    parser.add_argument("--rebuild", action="store_true", help="重建索引")
    parser.add_argument("--include-jsonl", action="store_true", help="包含 doc_parser 输出的 JSONL")
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"❌ 目录不存在: {source}")
        return

    result = index_docs(source, rebuild=args.rebuild, include_jsonl=args.include_jsonl)
    print(f"✅ 索引完成")
    print(f"   文档: {result['docs']} 个")
    print(f"   分块: {result['chunks']} 个")
    print(f"   字符: {result['chars']:,}")
    print(f"   向量: 512维 HNSW 索引")
    print(f"   耗时: {result['embed_seconds']}s")
    print(f"   数据库: {DB_PATH}")


if __name__ == "__main__":
    main()

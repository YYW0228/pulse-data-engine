"""
scripts/compliance_index.py — 合规文档索引器

把 china-ai-governance 的 md 文档按标题分块 → DuckDB
供 RAG 问答检索。

用法:
  uv run python -m scripts.compliance_index
  uv run python -m scripts.compliance_index --source /root/projects/china-ai-governance/ai-governance-legal/references
"""

import argparse
from pathlib import Path

import duckdb

DB_PATH = Path("data/compliance.duckdb")


def split_markdown(text: str, min_chars: int = 200) -> list[dict]:
    """按 ## 标题切分 md 文档为块"""
    blocks = []
    lines = text.splitlines()
    current_title = "文档头部"
    current_content: list[str] = []

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

    return blocks


def index_docs(source: Path) -> dict:
    """索引目录下所有 md 文档"""
    con = duckdb.connect(str(DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS compliance_chunks (
            doc_id INTEGER,
            doc_name VARCHAR,
            title VARCHAR,
            content VARCHAR,
            char_len INTEGER
        )
    """)
    con.execute("DELETE FROM compliance_chunks")

    files = sorted(source.rglob("*.md"))
    doc_id = 0
    total_chunks = 0
    total_chars = 0

    for f in files:
        doc_id += 1
        text = f.read_text(encoding="utf-8")
        blocks = split_markdown(text)
        for b in blocks:
            total_chunks += 1
            total_chars += len(b["content"])
            con.execute(
                "INSERT INTO compliance_chunks VALUES (?,?,?,?,?)",
                [doc_id, f.name, b["title"], b["content"], len(b["content"])],
            )

    con.close()
    return {"docs": doc_id, "chunks": total_chunks, "chars": total_chars}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        default="/root/projects/china-ai-governance/ai-governance-legal/references",
        help="md 文档目录",
    )
    args = parser.parse_args()

    source = Path(args.source)
    if not source.exists():
        print(f"❌ 目录不存在: {source}")
        return

    result = index_docs(source)
    print(f"✅ 索引完成")
    print(f"   文档: {result['docs']} 个")
    print(f"   分块: {result['chunks']} 个")
    print(f"   字符: {result['chars']:,}")
    print(f"   数据库: {DB_PATH}")


if __name__ == "__main__":
    main()

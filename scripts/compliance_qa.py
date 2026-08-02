"""
scripts/compliance_qa.py — 合规文档问答 (RAG 最小闭环)

用法:
  uv run python -m scripts.compliance_qa "算法备案的要求是什么"
  uv run python -m scripts.compliance_qa --query "..." --top-k 3
"""

import argparse
import json
import os
import re
from pathlib import Path

import duckdb

DB_PATH = Path("data/compliance.duckdb")

def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """向量语义检索 — DuckDB VSS 余弦相似度"""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    qvec = model.encode(query, normalize_embeddings=True)

    con = duckdb.connect(str(DB_PATH))
    con.execute("LOAD vss")
    con.execute("SET hnsw_enable_experimental_persistence = true")
    rows = con.execute(f"""
        SELECT doc_name, title, content, char_len,
               list_cosine_similarity(embedding, ?) as sim
        FROM compliance_chunks
        ORDER BY sim DESC
        LIMIT {top_k * 2}
    """, [qvec.tolist()]).fetchall()
    con.close()

    return [
        {"doc": d, "title": t, "content": c[:3000], "hits": round(float(s), 3)}
        for d, t, c, _clen, s in rows
    ]


def _get_api_key() -> str | None:
    """从环境变量或 .env 读取 DeepSeek key"""
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key
    for env_path in (Path.home() / ".hermes" / ".env", Path(".env")):
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return None


def answer(query: str, top_k: int = 3) -> str:
    """检索 + DeepSeek 回答 (带引用)"""
    chunks = retrieve(query, top_k)
    if not chunks:
        return "未找到相关文档。换个问法试试。"

    # 构建上下文
    context = "\n\n---\n\n".join(
        f"[文档: {c['doc']} | 章节: {c['title']}]\n{c['content']}" for c in chunks
    )

    api_key = _get_api_key()
    if not api_key:
        # 无 key 降级: 直接返回检索结果
        parts = [f"【{c['title']}】(来自 {c['doc']})\n{c['content'][:500]}" for c in chunks]
        return "检索到以下相关内容 (未配置 DEEPSEEK_API_KEY, 直接展示原文):\n\n" + "\n\n".join(parts)

    import httpx

    prompt = f"""你是企业 AI 合规顾问。基于以下参考资料回答用户问题。
规则:
1. 只依据参考资料回答, 资料没有的不编造
2. 回答末尾列出引用来源 (文档名+章节)
3. 不确定时明确说"资料中未找到"

参考资料:
{context}

问题: {query}
"""

    resp = httpx.post(
        "https://api.deepseek.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000,
        },
        timeout=60,
    )
    data = resp.json()
    return data["choices"][0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", default="算法备案的要求是什么")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = answer(args.query, args.top_k)
    if args.json:
        print(json.dumps({"query": args.query, "answer": result}, ensure_ascii=False, indent=2))
    else:
        print(f"Q: {args.query}\n")
        print(result)


if __name__ == "__main__":
    main()

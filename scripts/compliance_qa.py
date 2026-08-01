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
    """关键词检索 — 从合规文档库找相关块"""
    # 中文关键词提取: 优先 4 字词, 过滤垃圾碎片
    stopwords = {"的", "了", "是", "什么", "怎么", "如何", "要求", "需要", "应该", "一个", "这个", "那个", "我们", "你们", "他们", "吗", "呢", "啊", "吧", "与", "和", "及", "对", "在", "有", "要", "服务", "生成"}

    def _clean(seg: str) -> bool:
        """过滤无意义碎片: 含停用字/单字重复/纯字母杂音"""
        if any(s in seg for s in stopwords):
            return False
        return len(set(seg)) > 1  # "AAA" 或 "AA" 无意义

    keywords: set[str] = set()
    # 第一轮: 4 字词
    for start in range(len(query) - 3):
        seg = query[start:start+4]
        if _clean(seg):
            keywords.add(seg)
    # 第二轮: 补 3 字词 (4字词不足时)
    if len(keywords) < 6:
        for start in range(len(query) - 2):
            seg = query[start:start+3]
            if _clean(seg):
                keywords.add(seg)
    # 第三轮: 英文/数字专词
    for m in re.finditer(r"[A-Za-z]{2,}|\d+", query):
        keywords.add(m.group())
    keywords = {k for k in keywords if len(k) >= 2}
    if not keywords:
        keywords = {"AI"}  # 兜底
    keywords = list(keywords)[:15]
    # SQL 检索: 包含任意关键词, 标题命中加权
    conditions = " OR ".join(f"content LIKE '%{k}%'" for k in keywords)
    title_conditions = " OR ".join(f"title LIKE '%{k}%'" for k in keywords)
    con = duckdb.connect(str(DB_PATH))
    rows = con.execute(f"""
        SELECT doc_name, title, content, char_len,
               CASE WHEN {title_conditions} THEN 3 ELSE 0 END as title_bonus
        FROM compliance_chunks
        WHERE {conditions}
        ORDER BY title_bonus DESC, char_len ASC
        LIMIT {top_k * 15}
    """).fetchall()
    con.close()

    # 打分: 命中关键词数 + 标题命中加权 + 长度惩罚 (过短块不相关)
    scored = []
    for doc, title, content, clen, tbonus in rows:
        hits = sum(1 for k in keywords if k in content)
        # 长度惩罚: <50 字太短, >4000 太散
        len_penalty = 0
        if clen < 80:
            len_penalty = -2
        elif clen > 4000:
            len_penalty = -1
        scored.append((hits * 2 + tbonus + len_penalty, doc, title, content, clen))
    scored.sort(key=lambda x: -x[0])

    # 按文档去重: 同一文档最多取 3 块 (LLM 自己判断哪块最相关)
    doc_counts: dict[str, int] = {}
    deduped = []
    for score, doc, title, content, clen in scored:
        doc_counts[doc] = doc_counts.get(doc, 0) + 1
        if doc_counts[doc] <= 3:
            deduped.append((score, doc, title, content, clen))

    return [
        {"doc": d, "title": t, "content": c[:3000], "hits": h}
        for h, d, t, c, _ in deduped[:top_k]
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

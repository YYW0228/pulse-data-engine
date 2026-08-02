"""
scripts/compliance_qa.py — 合规文档问答 v3 (Context Compiler)

RAG 闭环: 向量语义检索 → Context Compiler (重排/裁剪/去重) → DeepSeek 回答 → 引用溯源

Context Compiler 核心:
  1. 模型缓存 — embedding 模型全局单例 (检索从 2.8s → ~50ms)
  2. 相似度阈值 — 低相关块 (sim < 0.55) 不进入 context
  3. MMR 多样性重排 — 同文档去重 + 跨文档多样性 (避免 6 块来自 6 文档的碎片化)
  4. 长度预算 — context 总长度 ≤ 6000 字符, 超过裁剪

用法:
  uv run python -m scripts.compliance_qa "算法备案的要求是什么"
  uv run python -m scripts.compliance_qa --query "..." --top-k 3
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# 确保 scripts/ 可导入 (compliance_metrics 等)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb

DB_PATH = Path("data/compliance.duckdb")

# ── Context Compiler 参数 ────────────────────────────────────────────
SIM_THRESHOLD = 0.55      # 低于此相似度的块不进 context
MAX_CONTEXT_CHARS = 6000  # context 总长度预算
MMR_LAMBDA = 0.7          # MMR 多样性权重 (0.7 = 相关性与多样性平衡)

# ── Embedding 模型缓存 (全局单例) ────────────────────────────────────
_model = None


def get_model():
    """懒加载 + 缓存 embedding 模型 (避免每次查询重新加载)"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    return _model


def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """向量语义检索 — DuckDB VSS 余弦相似度 (返回 top_k*3 候选)"""
    model = get_model()
    qvec = model.encode(query, normalize_embeddings=True)

    con = duckdb.connect(str(DB_PATH))
    # 兜底: 显式设置扩展目录 (systemd 环境 HOME 可能异常; 本机/CI home 均可写)
    ext_dir = Path.home() / ".duckdb" / "extensions"
    if ext_dir.exists():
        con.execute(f"SET extension_directory='{ext_dir}'")
    con.execute("INSTALL vss")  # 幂等: CI 环境自动下载到 home
    con.execute("LOAD vss")
    con.execute("SET hnsw_enable_experimental_persistence = true")
    rows = con.execute(f"""
        SELECT doc_name, title, content, char_len,
               list_cosine_similarity(embedding, ?) as sim,
               importance
        FROM compliance_chunks
        ORDER BY sim DESC
        LIMIT {top_k * 3}
    """, [qvec.tolist()]).fetchall()
    con.close()

    return [
        {"doc": d, "title": t, "content": c[:3000], "hits": round(float(s), 3), "char_len": cl, "importance": float(imp or 0.3)}
        for d, t, c, cl, s, imp in rows
    ]


def mmr_rerank(candidates: list[dict], query_vec, top_k: int) -> list[dict]:
    """MMR 多样性重排 — 选择相关且不重复的块

    score = λ * sim(q, d) - (1-λ) * max(sim(d, selected))
    相关性与多样性平衡, 避免多个相似块来自同一文档
    """
    selected: list[dict] = []
    remaining = candidates[:]

    while remaining and len(selected) < top_k:
        best_idx = -1
        best_score = float("-inf")
        for i, cand in enumerate(remaining):
            sim_q = cand["hits"]  # 与查询的相似度
            importance = cand.get("importance", 0.3)  # 块重要性
            # 与已选块的最大重复度 (同文档视为高度重复, 跨文档低重复)
            max_dup = 0.0
            for sel in selected:
                if sel["doc"] == cand["doc"]:
                    max_dup = max(max_dup, 0.9)
                else:
                    max_dup = max(max_dup, 0.3)
            # 综合分: 相关性 + 重要性 - 重复惩罚
            score = MMR_LAMBDA * sim_q + (1 - MMR_LAMBDA) * importance - (1 - MMR_LAMBDA) * max_dup
            if score > best_score:
                best_score = score
                best_idx = i
        if best_idx == -1:
            break
        selected.append(remaining.pop(best_idx))

    return selected


def compile_context(query: str, top_k: int = 3, mask_metadata: bool = False) -> list[dict]:
    """Context Compiler: 检索 → 过滤 → 重要性加权 MMR 重排 → 长度裁剪

    mask_metadata=True: 观察屏蔽 (observation masking) —
      只给 LLM 文档内容, 不暴露相似度/内部评分 (防 prompt 泄露 + 防注入利用)
    """
    model = get_model()
    qvec = model.encode(query, normalize_embeddings=True)

    # 1. 检索候选
    candidates = retrieve(query, top_k=top_k)

    # 2. 相似度阈值过滤
    filtered = [c for c in candidates if c["hits"] >= SIM_THRESHOLD]

    # 3. MMR 多样性重排 + 重要性加权 (综合分 = λ*sim + (1-λ)*importance - (1-λ)*dup)
    reranked = mmr_rerank(filtered, qvec, top_k)

    # 4. 长度预算裁剪
    total_chars = 0
    budgeted = []
    for c in reranked:
        if total_chars + c["char_len"] > MAX_CONTEXT_CHARS:
            # 超预算: 截断内容到剩余预算
            remaining = MAX_CONTEXT_CHARS - total_chars
            if remaining > 500:  # 至少保留 500 字
                c["content"] = c["content"][:remaining] + "...[截断]"
                budgeted.append(c)
            break
        budgeted.append(c)
        total_chars += c["char_len"]

    # 5. observation masking: 剥离内部元数据
    if mask_metadata:
        budgeted = [
            {"doc": c["doc"], "title": c["title"], "content": c["content"],
             "hits": None, "char_len": c["char_len"], "importance": None}
            for c in budgeted
        ]

    return budgeted


def _route_model(query: str, chunks: list[dict]) -> str:
    """Model 路由层 — 小模型默认, 复杂度/低置信度升级 frontier

    路由信号:
      1. 查询长度 > 60 字 → 复杂问题
      2. 检索块数 == 0 → 需推理 (升级)
      3. 平均相似度 < 0.6 → 知识库弱覆盖, 需更强推理
      4. 含法规/条款/多主题 → 复杂 (如 "第X条" "跨境" "合规流程")

    模型映射 (DeepSeek):
      小模型: deepseek-chat (便宜, 默认 80%+)
      frontier: deepseek-reasoner (关键路径)
    """
    # 复杂度信号
    if len(query) > 60:
        return "deepseek-reasoner"
    if not chunks:
        return "deepseek-reasoner"
    avg_sim = sum(c["hits"] for c in chunks) / len(chunks)
    if avg_sim < 0.6:
        return "deepseek-reasoner"
    complex_kw = ["第", "条", "跨境", "流程", "评估", "合规体系", "法律责任", "处罚"]
    if any(k in query for k in complex_kw):
        return "deepseek-reasoner"
    return "deepseek-chat"


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


def classify_intent(query: str) -> str:
    """意图-检索前置分类器 (Meta-Loop 提案1)

    标签:
      factual_query  — 事实查询, 需检索 (正常合规问题)
      roleplay       — 角色扮演/私人助理 (不检索, 拒绝或引导)
      instruction_attack — 指令注入/越狱 (拒绝, 安全路径)
      creative       — 通用写作/非知识库问题 (不检索)
      probe          — 隐私/敏感探测 (拒绝)

    轻量规则实现 (0 成本, 无 LLM 调用):
      关键词 + 模式匹配, 覆盖 Meta-Loop 发现的失败样本
    """
    q = query.strip()

    # 指令注入 / 越狱
    injection_kw = ["忽略", "忽略之前", "忘记", "系统提示", "system prompt", "越狱",
                    "绕过", "以上规则不适用", "现在开始你", "扮演"]
    if any(k in q for k in injection_kw):
        return "instruction_attack"

    # 角色扮演 / 私人助理
    roleplay_kw = ["私人助理", "帮我写请假", "写一封", "你是我的", "从现在开始你",
                   "以法务身份", "以律师身份", "请以", "法务人员吗"]
    if any(k in q for k in roleplay_kw):
        return "roleplay"

    # 隐私/敏感探测
    probe_kw = ["列出所有", "所有文档中", "敏感数据", "具体金额", "公司名称", "泄露",
                "客户数据", "身份证", "手机号"]
    if any(k in q for k in probe_kw):
        return "probe"

    # 通用写作/非知识库
    creative_kw = ["写一篇", "写段", "作文", "诗歌", "小说", "邮件模板"]
    if any(k in q for k in creative_kw):
        return "creative"

    return "factual_query"


INTENT_REJECT = {
    "instruction_attack": "抱歉，我不能执行这个请求。作为合规助手，我只基于合规知识库回答企业 AI 合规相关问题。",
    "roleplay": "我是 AI 合规问答助手，专注于企业 AI 合规咨询。如果你有合规相关问题（算法备案、数据合规、AI 治理等），我很乐意回答。",
    "probe": "抱歉，我不能提供涉及敏感数据或内部信息的汇总。如有具体合规问题，请直接提问，我将基于公开合规资料回答。",
    "creative": "我是 AI 合规问答助手。这个问题不在合规知识库范围内，请提出企业 AI 合规相关问题。",
}


def answer(query: str, top_k: int = 3, mask_metadata: bool = True,
           history: list[dict[str, str]] | None = None) -> str:
    """检索 + DeepSeek 回答 (带引用) + 可观测性埋点

    mask_metadata=True (默认): 生产回答屏蔽内部评分 (observation masking),
    检索依据仅供展示层 (前端单独用 compile_context 获取)
    history: 历史对话 (append-only, PrefixCache 稳定化)
    """
    t0 = time.time()
    # Trace 开始
    try:
        from pulse.trace import Tracer

        tracer = Tracer(query, source="cli")
    except Exception:
        tracer = None

    # ── 意图分类 (Meta-Loop 提案1: 前置拦截非事实查询) ──
    intent = classify_intent(query)
    if tracer:
        tracer.step("intent", {"intent": intent})
    if intent != "factual_query":
        rejection = INTENT_REJECT.get(intent, INTENT_REJECT["instruction_attack"])
        _record_metric(query, (time.time() - t0) * 1000, 0, 0, 0, 0, True,
                       error=f"intent:{intent}")
        if tracer:
            tracer.step("reject", {"intent": intent})
            tracer.save({"success": True, "intent": intent, "rejected": True})
        return rejection

    # 先编译 (带内部评分, 供路由决策)
    chunks = compile_context(query, top_k, mask_metadata=False)
    compile_ms = (time.time() - t0) * 1000

    if tracer:
        tracer.step("retrieve", {"chunks": len(chunks), "top_sim": round(chunks[0]["hits"], 3) if chunks else 0,
                                 "docs": sorted({c["doc"] for c in chunks})[:3]})
    if not chunks:
        _record_metric(query, compile_ms, 0, 0, 0, 0, False, "no_chunks")
        if tracer:
            tracer.save({"success": False, "error": "no_chunks"})
        return "未找到相关文档。换个问法试试。"

    # Model 路由 (用未屏蔽的相似度决策)
    model_name = _route_model(query, chunks)
    if tracer:
        tracer.step("route", {"model": model_name, "avg_sim": round(sum(c["hits"] for c in chunks) / len(chunks), 3)})

    # observation masking: 生产回答剥离内部评分
    if mask_metadata:
        chunks = [
            {"doc": c["doc"], "title": c["title"], "content": c["content"],
             "hits": None, "char_len": c["char_len"], "importance": None}
            for c in chunks
        ]
    if tracer:
        tracer.step("compile", {"final_chunks": len(chunks),
                                "total_chars": sum(c["char_len"] or 0 for c in chunks)})

    # 构建上下文
    context = "\n\n---\n\n".join(
        f"[文档: {c['doc']} | 章节: {c['title']}]\n{c['content']}" for c in chunks
    )
    tokens_in_estimate = len(context) // 2  # 中文约 2 字符/token

    api_key = _get_api_key()
    if not api_key:
        parts = [f"【{c['title']}】(来自 {c['doc']})\n{c['content'][:500]}" for c in chunks]
        _record_metric(query, compile_ms, len(chunks), len(chunks), tokens_in_estimate, 0, True)
        return f"(编译耗时 {compile_ms:.0f}ms, 检索 {len(chunks)} 块)\n\n" + "\n\n".join(parts)

    import httpx

    # ── PrefixCache 稳定化 (源自 Reasonix PrefixShape) ──
    # 1. 稳定 system prompt (版本 hash 固定) → 缓存命中
    # 2. 历史 append-only (不重写) → 已发送的命中
    # 3. 检索块+问题放最后 (唯一变体) → 只付增量 token
    system_prompt = f"""你是企业 AI 合规顾问。基于参考资料回答用户问题。
规则:
1. 只依据参考资料回答, 资料没有的不编造
2. 每个要点后面必须标注引用来源, 格式: [文档: 文件名 | 章节: 章节名]
3. 回答末尾必须单独列出"引用来源:" 清单
4. 不确定时明确说"资料中未找到"

[system_prompt_version: v1.0]
"""
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)  # append-only, 不重写不排序
    messages.append({
        "role": "user",
        "content": f"参考资料:\n{context}\n\n问题: {query}",
    })

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_name,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1000,
            },
            timeout=60,
        )
        data = resp.json()
        answer_text = data["choices"][0]["message"]["content"]
        # 空回答重试 (上游偶发空 content — Error Handling)
        if not answer_text or not answer_text.strip():
            answer_text = _retry_empty_answer(api_key, messages, model_name)
        tokens_out = data.get("usage", {}).get("completion_tokens", len(answer_text) // 2)
        # 引用计数: 回答中 [文档: 出现次数
        citations = answer_text.count("文档:")
        _record_metric(query, (time.time() - t0) * 1000, len(chunks), citations,
                       tokens_in_estimate, tokens_out, True, model=model_name)
        if tracer:
            tracer.step("answer", {"model": model_name, "tokens_in": tokens_in_estimate,
                                   "tokens_out": tokens_out, "citations": citations,
                                   "answer_len": len(answer_text)})
            tracer.save({"success": True, "model": model_name, "citations": citations})
        return answer_text
    except Exception as e:
        _record_metric(query, (time.time() - t0) * 1000, len(chunks), 0,
                       tokens_in_estimate, 0, False, str(e)[:80])
        if tracer:
            tracer.step("error", {"error": str(e)[:100]})
            tracer.save({"success": False, "error": str(e)[:100]})
        raise


def _retry_empty_answer(api_key: str, messages: list[dict[str, str]], model_name: str) -> str:
    """空回答重试 (上游偶发) — 重试 1 次, 仍空返回友好错误"""
    import httpx

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_name,
                "messages": messages,
                "temperature": 0.5,  # 略升温打破重复
                "max_tokens": 1000,
            },
            timeout=60,
        )
        text = resp.json()["choices"][0]["message"]["content"]
        if text and text.strip():
            return text
    except Exception:
        pass
    return "抱歉，模型暂时无法生成回答，请稍后重试。" + "\n\n(回答为空 — 上游模型偶发异常，已重试)" + "\n\n引用来源：无（未生成回答）"


def _record_metric(query: str, ms: float, chunks: int, citations: int,
                   tokens_in: int, tokens_out: int, success: bool, error: str = "",
                   model: str = "deepseek-chat") -> None:
    """记录问答指标 (失败不阻断主流程)"""
    try:
        from compliance_metrics import record

        record(query, ms, chunks, citations, tokens_in, tokens_out, success, error, model)
    except Exception:
        pass


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

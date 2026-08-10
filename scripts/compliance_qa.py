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
import re
import sys
import time
from pathlib import Path

# 确保 scripts/ 可导入 (compliance_metrics 等)
sys.path.insert(0, str(Path(__file__).resolve().parent))

import duckdb

DB_PATH = Path("data/compliance.duckdb")
# 客户库查询 (compliance_index --db <name> 建的独立库)
_CUSTOMER_DB: str | None = None


def set_customer_db(db: str | None) -> None:
    """切换客户库 (data/customers/<db>/<db>.duckdb), None=全局库"""
    global _CUSTOMER_DB
    _CUSTOMER_DB = db


def _active_db() -> Path:
    if _CUSTOMER_DB:
        return Path(f"data/customers/{_CUSTOMER_DB}/{_CUSTOMER_DB}.duckdb")
    return DB_PATH

# ── Context Compiler 参数 ────────────────────────────────────────────
SIM_THRESHOLD = 0.55      # 低于此相似度的块不进 context
MAX_CONTEXT_CHARS = 6000  # context 总长度预算
LARGE_CHUNK_CHARS = 4000  # 单块超过此长度 → 转存文件 (reactive_compaction)
HANDOFF_THRESHOLD = 8     # history 超过 8 轮 → 生成交接摘要 (T6, buzz 模式)
DUMP_DIR = Path(__file__).resolve().parent.parent / "data" / "context_dumps"


def _dump_large_chunk(doc: str, title: str, content: str) -> str:
    """大块转存: 返回落盘路径 (mini-claude-code toolResultBudget 思路)"""
    try:
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^\w\-]", "_", f"{doc[:30]}_{title[:20]}")[:60]
        path = DUMP_DIR / f"{safe}.md"
        path.write_text(f"# {doc} — {title}\n\n{content}", encoding="utf-8")
        return str(path)
    except Exception:
        return "context_dumps/"
MMR_LAMBDA = 0.8          # MMR 多样性权重 (0.8 = 更贴题, A/B 通过 2026-08-10)

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
    """向量语义检索 — DuckDB VSS 余弦相似度 (返回 top_k*3 候选)

    客户库回退: 客户库无有效命中 (<SIM_THRESHOLD) → 自动回退全局库
    (客户库 = 客户文档 + 全局法规底座)
    """
    model = get_model()
    qvec = model.encode(query, normalize_embeddings=True)

    def _query(db_path: Path) -> list[dict]:
        con = duckdb.connect(str(db_path))
        ext_dir = Path.home() / ".duckdb" / "extensions"
        if ext_dir.exists():
            con.execute(f"SET extension_directory='{ext_dir}'")
        con.execute("INSTALL vss")
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
            {"doc": d, "title": t, "content": c[:3000], "hits": round(float(s), 3),
             "char_len": cl, "importance": float(imp or 0.3)}
            for d, t, c, cl, s, imp in rows
        ]

    results = _query(_active_db())

    # 客户库回退: 客户库命中明显弱于全局库 (答非所问) → 全局库优先
    # 判定: 全局库最高 sim - 客户库最高 sim > 0.05 → 客户库内容不匹配
    if _CUSTOMER_DB and results:
        global_results = _query(DB_PATH)
        cust_best = max(r["hits"] for r in results)
        global_best = max((r["hits"] for r in global_results), default=0.0)
        if global_best - cust_best > 0.05 and global_best >= SIM_THRESHOLD:
            valid_global = [r for r in global_results if r["hits"] >= SIM_THRESHOLD]
            if valid_global:
                return valid_global

    return results


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

    # 4. 长度预算裁剪 + 大输出存盘 (reactive_compaction Layer 1: 源自 mini-claude-code)
    total_chars = 0
    budgeted = []
    for c in reranked:
        # 大块 (>LARGE_CHUNK_CHARS) 转存文件, 上下文只留路径+预览
        if c["char_len"] > LARGE_CHUNK_CHARS:
            dump_path = _dump_large_chunk(c["doc"], c["title"], c["content"])
            c["content"] = f"[大文档已转存: {dump_path}]\n预览: {c['content'][:500]}..."
            c["char_len"] = min(c["char_len"], 800)
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
    # 隐私/敏感探测 (需组合特征: 枚举意图 + 敏感词, 防误伤制度问答)
    probe_kw = ["列出所有", "所有文档中", "汇总所有", "全部敏感", "所有客户的", "全部数据"]
    if any(k in q for k in probe_kw):
        return "probe"

    # 通用写作/非知识库
    creative_kw = ["写一篇", "写段", "作文", "诗歌", "小说", "邮件模板"]
    if any(k in q for k in creative_kw):
        return "creative"

    # 元问题 (关于系统本身 — 信任/能力/来源, 不检索直接回答)
    meta_kw = ["有多少把握", "谁负责", "怎么保证", "怎么证明", "信息来源",
               "数据来源", "准确吗", "可靠吗", "最新的吗", "多久更新",
               "和chatgpt", "和 chatgpt", "有什么区别", "是你做的吗",
               "你的原理", "你会出错", "错了怎么办", "怎么更新"]
    if any(k in q for k in meta_kw):
        return "meta"

    return "factual_query"


INTENT_REJECT = {
    "instruction_attack": "抱歉，我不能执行这个请求。作为合规助手，我只基于合规知识库回答企业 AI 合规相关问题。",
    "roleplay": "我是 AI 合规问答助手，专注于企业 AI 合规咨询。如果你有合规相关问题（算法备案、数据合规、AI 治理等），我很乐意回答。",
    "probe": "抱歉，我不能提供涉及敏感数据或内部信息的汇总。如有具体合规问题，请直接提问，我将基于公开合规资料回答。",
    "creative": "我是 AI 合规问答助手。这个问题不在合规知识库范围内，请提出企业 AI 合规相关问题。",
    "meta": "我是基于法规知识库的 AI 合规问答助手。关于我的能力和局限：\n\n1. **信息来源**: 回答基于企业法规知识库 (算法备案/深度合成/生成式AI/数据跨境等公开法规 + 每日更新的监管情报管道)\n2. **更新机制**: 情报管道每 12 小时自动采集 (网信办官网/权威媒体), 每日 04:00 增量入库\n3. **准确度**: 每个回答带引用溯源 [文档: 章节], 可回溯原文; 关键决策请以国家网信办官网 (cac.gov.cn) 为准\n4. **局限**: 知识库未覆盖的问题会明确说\"未找到\", 不编造; 具体企业个案建议结合专业律师意见\n\n**我的价值**: 把\"查法规\"从 2 小时变成 3 秒, 且每条答案可溯源验证。",
}

# Loop Detection 单例 (DeerFlow 模式: 重复检索模式 → 终止)
try:
    from experiments.loop_detection import LoopDetector

    _loop_detector: LoopDetector | None = LoopDetector(window_size=10, warn_threshold=3, hard_threshold=5)
except Exception:
    _loop_detector = None


def _generate_handoff(history: list[dict[str, str]], api_key: str, model_name: str,
                      tracer) -> str | None:
    """T6: 生成上下文交接摘要 (buzz handoff.rs 模式)

    长对话 (>HANDOFF_THRESHOLD 轮) → LLM 提炼: 原任务/已完成/下一步
    摘要替代旧消息, 保留最近一轮 → token 大降 + 状态不丢
    """
    if not api_key:
        return None
    import httpx  # 局部导入 (与文件其他函数一致, 避免启动开销)

    # 只取最近的对话做摘要 (全量太长)
    recent = history[-10:]
    compact = "\n".join(
        f"{m['role']}: {m['content'][:200]}" for m in recent
    )
    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": (
                        "You are generating a context handoff summary for the next "
                        "turn of an assistant. Be concise but thorough. Cover: "
                        "1) what the original task was, 2) what was already done, "
                        "3) what is next / open questions. Output in Chinese, "
                        "under 200 words.")},
                    {"role": "user", "content": compact},
                ],
                "temperature": 0.2,
                "max_tokens": 300,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"].strip()
        if tracer:
            tracer.step("handoff", {"summary_len": len(text)})
        return f"[会话交接摘要] {text}"
    except Exception:
        return None


def answer(query: str, top_k: int = 3, mask_metadata: bool = True,
           history: list[dict[str, str]] | None = None,
           budget: dict | None = None) -> str:
    """检索 + DeepSeek 回答 (带引用) + 可观测性埋点

    mask_metadata=True (默认): 生产回答屏蔽内部评分 (observation masking),
    检索依据仅供展示层 (前端单独用 compile_context 获取)
    history: 历史对话 (append-only, PrefixCache 稳定化)
    budget: token 预算闸门 {max_tokens_in, max_tokens_out} (超限 capped)
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
        _record_metric(query, (time.time() - t0) * 1000, 0, 0, None, None, True,
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
        _record_metric(query, compile_ms, 0, 0, None, None, False, "no_chunks")
        if tracer:
            tracer.save({"success": False, "error": "no_chunks"})
        return ("未找到相关文档。换个问法试试。\n\n"
                "💡 提示: 如果是查询具体模型/企业的备案状态 (事实性信息), "
                "知识库可能未收录最新备案清单。可:\n"
                "1. 到国家网信办官网备案系统核查\n"
                "2. 联系我们补充该数据源到知识库")

    # ── Token Budget 闸门 (源自 DeerFlow, 超限 capped 不抛异常) ──
    if budget:
        try:
            from experiments.token_budget import TokenBudget

            check = TokenBudget(**budget).check()
            if not check["allowed"]:
                _record_metric(query, (time.time() - t0) * 1000, 0, 0, 0, 0,
                               True, error=f"budget:{check['reason']}")
                return f"⚠️ 会话预算已用尽 ({check['reason']})。请开始新会话。\n\n引用来源：无（预算限制）"
        except Exception:
            pass  # 预算检查失败不阻断

    # Model 路由 (用未屏蔽的相似度决策)
    model_name = _route_model(query, chunks)

    # ── Loop Detection (源自 DeerFlow: 重复检索模式 → 终止) ──
    try:
        from experiments.loop_detection import LoopDetector

        fp = LoopDetector.fingerprint(query, [c["doc"] for c in chunks])
        status = _loop_detector.record(fp) if _loop_detector else "ok"
        if status == "capped":
            _record_metric(query, (time.time() - t0) * 1000, len(chunks), 0, 0, 0,
                           True, error="loop_capped")
            return "⚠️ 检测到重复检索循环 (loop_capped)，已停止以避免浪费。请换一种问法或开始新话题。\n\n引用来源：无（循环终止）"
    except Exception:
        pass  # 循环检测失败不阻断

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
        # T6 Handoff: history 过长 (>HANDOFF_THRESHOLD 轮) → 生成交接摘要 (buzz 模式)
        if len(history) > HANDOFF_THRESHOLD:
            summary = _generate_handoff(history, api_key, model_name, tracer)
            if summary:
                messages.append({"role": "system", "content": summary})
                messages.extend(history[-2:])  # 保留最近一轮完整对话
            else:
                messages.extend(history)  # 摘要失败 → 原样 (降级)
        else:
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
        # 反应式压缩: prompt_is_too_long → 截断 history 重试 (mini-claude-code)
        if resp.status_code == 400 and "prompt_is_too_long" in resp.text:
            compacted = _reactive_compact(messages, history)
            if compacted is not None:
                return _llm_call_with_retry(api_key, compacted, model_name, query, chunks,
                                            history, t0, tracer)
        answer_text = data["choices"][0]["message"]["content"]
        # 空回答重试 (上游偶发空 content — Error Handling)
        if not answer_text or not answer_text.strip():
            answer_text = _retry_empty_answer(api_key, messages, model_name)
        tokens_out = data.get("usage", {}).get("completion_tokens", len(answer_text) // 2)
        # 引用计数: 回答中 [文档: 出现次数
        citations = answer_text.count("文档:")
        # PrefixCache 命中估算: 有 history (追加式) → 前缀稳定 → 命中
        cache_hit = bool(history)
        _record_metric(query, (time.time() - t0) * 1000, len(chunks), citations,
                       tokens_in_estimate, tokens_out, True, model=model_name,
                       cache_hit=cache_hit)
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


def _reactive_compact(messages: list[dict], history: list[dict] | None) -> list[dict] | None:
    """反应式压缩: prompt_is_too_long → 保留 system + 最近 4 轮, 其余丢弃
    (mini-claude-code 思路: 错误永不暴露给用户)"""
    try:
        if not history or len(history) <= 6:
            return None  # 历史太短, 压缩无意义
        keep = history[-6:]  # 保留最近 3 轮 (user+assistant 对)
        compacted = [messages[0]] + keep
        # 重新组装当前问题消息 (最后一个 user 消息保留完整内容)
        for m in messages[-1:]:
            compacted.append(m)
        return compacted
    except Exception:
        return None


def _llm_call_with_retry(api_key: str, messages: list[dict], model_name: str,
                         query: str, chunks: list[dict], history: list[dict] | None,
                         t0: float, tracer) -> str:
    """压缩后重发请求 (反应式压缩的第二阶段)"""
    import httpx

    try:
        resp = httpx.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": model_name, "messages": messages,
                  "temperature": 0.3, "max_tokens": 1000},
            timeout=60,
        )
        data = resp.json()
        answer_text = data["choices"][0]["message"]["content"]
        tokens_out = data.get("usage", {}).get("completion_tokens", len(answer_text) // 2)
        citations = answer_text.count("文档:")
        _record_metric(query, (time.time() - t0) * 1000, len(chunks), citations,
                       len(json.dumps(messages, ensure_ascii=False)) // 2, tokens_out,
                       True, model=model_name, cache_hit=bool(history),
                       reactive_compact=True)
        if tracer:
            tracer.step("reactive_compact", {"tokens_out": tokens_out, "citations": citations})
            tracer.save({"success": True, "model": model_name, "citations": citations,
                         "reactive_compact": True})
        return answer_text
    except Exception:
        return "抱歉，上下文过长且压缩重试失败，请开始新对话。\n\n(上下文超限 — 已尝试自动压缩)"



def _record_metric(query: str, ms: float, chunks: int, citations: int,
                   tokens_in: int | None, tokens_out: int | None, success: bool,
                   error: str = "",
                   model: str = "deepseek-chat", cache_hit: bool | None = None,
                   reactive_compact: bool = False) -> None:
    """记录问答指标 (失败不阻断主流程)"""
    try:
        from compliance_metrics import record

        record(query, ms, chunks, citations, tokens_in, tokens_out, success, error,
               model, cache_hit, reactive_compact)
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

"""
serve_compliance.py — 合规问答助手 (Streamlit 前端)

用法:
  uv run streamlit run serve_compliance.py --server.port 8502
"""

import sys
from pathlib import Path

import streamlit as st

# 确保 scripts 可导入
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

st.set_page_config(page_title="AI 合规问答助手", page_icon="⚖️", layout="wide")

st.markdown(
    "<h1 style='text-align:center'>⚖️ AI 合规问答助手</h1>"
    "<p style='text-align:center;color:#888'>基于 30 份 AI 治理法规文档 · 向量语义检索 · 带引用溯源</p>",
    unsafe_allow_html=True,
)

# 侧边栏: 使用说明 + 示例问题
st.sidebar.markdown("## 使用说明")
st.sidebar.markdown(
    """
    输入企业 AI 合规问题, 助手会:
    1. 语义检索相关法规文档
    2. 基于文档生成回答
    3. 标注引用来源
    
    **示例问题:**
    - 算法备案的要求是什么？
    - 生成式AI的训练数据合规要求
    - 深度合成内容需要标识吗？
    - AI Agent 需要什么治理框架？
    - 跨境数据传输有什么限制？
    """
)

# ── 可观测性面板 (成本/效率仪表盘) ──────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("## 📈 成本与效率")
try:
    import sys as _sys
    from pathlib import Path as _Path

    _sys.path.insert(0, str(_Path(__file__).resolve().parent / "scripts"))
    from compliance_metrics import summarize

    s = summarize(limit=200)
    if s["total"] > 0:
        st.sidebar.metric("总问答", s["total"])
        st.sidebar.metric("成功率", f"{s['success_rate']*100:.0f}%")
        st.sidebar.metric("平均耗时", f"{s['avg_ms']:.0f}ms")
        st.sidebar.metric("平均 token", f"{s['avg_tokens_in']}→{s['avg_tokens_out']}")
        st.sidebar.metric("平均引用", f"{s['avg_citations']}")
        st.sidebar.metric("总成本", f"${s['total_cost_usd']:.4f}")
    else:
        st.sidebar.caption("暂无数据 — 先发一条问题")
except Exception:
    st.sidebar.caption("指标暂不可用")

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": '你好！我是 AI 合规问答助手。请输入你的合规问题，例如：\n\n**"算法备案的要求是什么？"**'}
    ]


def ask(query: str, history: list[dict[str, str]] | None = None) -> str:
    """调用 compliance_qa 回答 (含检索块调试信息 + 置信度评估 + 审批闸门)

    history: 多轮对话历史 (append-only, PrefixCache 稳定化)
    """
    from compliance_qa import answer, classify_intent, compile_context

    # 意图分类: 非事实查询直接拒绝 (不调 LLM)
    intent = classify_intent(query)
    if intent != "factual_query":
        from compliance_qa import INTENT_REJECT

        return INTENT_REJECT.get(intent, INTENT_REJECT["instruction_attack"])

    # 编译检索块 (供展示 + 置信度评估)
    chunks = []
    try:
        chunks = compile_context(query, top_k=3)
        debug = "\n\n---\n**📎 检索依据 (相似度):**\n"
        for c in chunks:
            debug += f"- `{c['doc'][:40]}` · {c['title'][:30]} · sim={c['hits']}\n"

        # 置信度评估: 平均相似度 < 0.6 → 低置信, 需人工审批闸门
        avg_sim = sum(c["hits"] for c in chunks) / max(len(chunks), 1) if chunks else 0
        if avg_sim < 0.6:
            debug += (
                f"\n⚠️ **低置信度审批闸门** (平均相似度 {avg_sim:.2f} < 0.6):\n"
                f"本回答将标记为『待人工复核』，不建议直接用于决策。\n"
                f"请合规专员确认后再引用。"
            )
    except Exception:
        debug = ""

    result = answer(query, history=history)

    # 审批流: 低置信度回答附加审批标记
    approval = ""
    try:
        avg_sim = sum(c["hits"] for c in chunks) / max(len(chunks), 1) if chunks else 0
        if avg_sim < 0.6:
            approval = "\n\n---\n**🛂 审批状态: 待人工复核** — 此回答基于低置信度检索生成，需合规专员确认后使用。"
    except Exception:
        pass

    return result + debug + approval


# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入框
if prompt := st.chat_input("输入你的合规问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("检索法规文档中..."):
            try:
                # 构建 append-only 历史 (PrefixCache 稳定化)
                history_msgs = []
                for m in st.session_state.messages[:-1]:  # 排除当前问题
                    if m["role"] in ("user", "assistant") and isinstance(m["content"], str):
                        history_msgs.append({"role": m["role"], "content": m["content"][:4000]})
                response = ask(prompt, history=history_msgs[-8:])  # 最近 4 轮
            except Exception as e:
                response = f"❌ 回答失败: {e}\n\n请检查 embedding 模型和 DEEPSEEK_API_KEY 配置。"

        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

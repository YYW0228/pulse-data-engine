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

# 初始化会话状态
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": '你好！我是 AI 合规问答助手。请输入你的合规问题，例如：\n\n**"算法备案的要求是什么？"**'}
    ]


def ask(query: str) -> str:
    """调用 compliance_qa 回答"""
    from compliance_qa import answer

    return answer(query)


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
                response = ask(prompt)
            except Exception as e:
                response = f"❌ 回答失败: {e}\n\n请检查 embedding 模型和 DEEPSEEK_API_KEY 配置。"

        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

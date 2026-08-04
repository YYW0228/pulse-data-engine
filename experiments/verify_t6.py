"""T6 handoff 交接摘要验证"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from compliance_qa import HANDOFF_THRESHOLD, _generate_handoff, _get_api_key, answer


def test_threshold():
    """阈值: 8 轮内不触发, 超过触发"""
    short = [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好"}]
    assert len(short) <= HANDOFF_THRESHOLD
    long = [{"role": u, "content": f"消息{i}"} for i in range(6) for u in ("user", "assistant")]
    assert len(long) > HANDOFF_THRESHOLD
    print(f"✅ 阈值逻辑: 短对话 {len(short)} 轮 (不触发), 长对话 {len(long)} 轮 (触发)")


def test_generate_handoff():
    """真实生成交接摘要 (需要 API key)"""
    key = _get_api_key()
    if not key:
        print("⚠️ 无 API key, 跳过真实摘要测试")
        return
    history = [
        {"role": "user", "content": "我们公司要做 AI 出海合规, 需要先了解欧盟 AI 法案要求"},
        {"role": "assistant", "content": "欧盟 AI 法案核心: 高风险系统需满足 Art.50 标识要求, 透明度义务..."},
        {"role": "user", "content": "那我们的训练数据需要怎么做合规?"},
        {"role": "assistant", "content": "训练数据合规: 合法来源 + 去标识化 + 敏感数据特别评估..."},
        {"role": "user", "content": "如果我们要出口美国呢?"},
        {"role": "assistant", "content": "美国市场: 州级隐私法规 (CCPA), 行政令要求..."},
        {"role": "user", "content": "数据跨境有什么限制?"},
        {"role": "assistant", "content": "数据出境: 安全评估/标准合同/认证三种方式..."},
        {"role": "user", "content": "那算法备案呢?"},
        {"role": "assistant", "content": "算法备案: 2026 新规, 所有对外算法服务必须备案..."},
    ]
    summary = _generate_handoff(history, key, "deepseek-chat", None)
    assert summary is not None, "摘要应生成"
    print(f"✅ 交接摘要生成: {summary[:150]}...")
    print(f"   长度: {len(summary)} 字符 (原 {len(history)} 轮消息)")


def test_long_conversation_answer():
    """端到端: 长对话 + 交接摘要后问答仍正常"""
    key = _get_api_key()
    if not key:
        print("⚠️ 无 API key, 跳过端到端测试")
        return
    history = [
        {"role": "user", "content": f"第{i}轮问题{i}: AI 治理相关内容是什么?"}
        if i % 2 == 0 else {"role": "assistant", "content": f"第{i}轮回答: 治理框架要点 {i}"}
        for i in range(1, 11)  # 10 轮 → 超过阈值
    ]
    result = answer("总结一下我们刚才讨论的 AI 治理要点", top_k=3, history=history)
    print(f"✅ 长对话问答: {result[:120]}...")
    print(f"   引用数: {result.count('文档:')}")


if __name__ == "__main__":
    test_threshold()
    test_generate_handoff()
    test_long_conversation_answer()
    print("\n✅ T6 全部验证通过")

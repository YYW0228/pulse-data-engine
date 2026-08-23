"""
tests/test_compaction_e2e.py — 压缩链路生产级验证

mock 真实 400 prompt_is_too_long 响应 → 验证 answer() 完整压缩链路:
handoff(200) → 主调用(400) → 压缩审计 start → 重发(200) → 审计 end。
断言: 审计流 start+end 配对 / 无孤儿 / 重发请求 messages 为压缩后内容。
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    """隔离: 审计写 tmp + 假 embedding (零 torch/网络)。"""
    import scripts.compliance_qa as cqa

    monkeypatch.setenv("LLM_AUDIT_PATH", str(tmp_path / "llm_audit.jsonl"))
    cqa._embedder = None

    def fake_build(name: str = "bge"):
        import numpy as np

        m = MagicMock()
        m._model_name = name
        m.encode.return_value = np.ones(512, dtype=np.float32)
        return m

    from pulse.component import ManagedComponent
    monkeypatch.setattr(
        cqa, "_embedder_component",
        lambda: ManagedComponent("embedding.test", lambda: fake_build()),
    )
    fake_st = types.ModuleType("sentence_transformers")
    fake_st.SentenceTransformer = fake_build
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_st)
    yield
    cqa._embedder = None


def _fake_resp(status: int, content: str):
    r = MagicMock()
    r.status_code = status
    r.text = "prompt_is_too_long" if status == 400 else ""
    if status >= 500:
        r.json.side_effect = ValueError("非 JSON 错误响应 (真实 500 行为)")
    else:
        r.json.return_value = {"choices": [{"message": {"content": content}}]}
    return r


def _fake_chunks():
    return [
        {"doc": "test-doc.md", "title": "测试章节", "content": "算法备案相关测试内容" * 20,
         "hits": 0.75, "char_len": 280, "importance": 0.3, "fetched_at": ""},
        {"doc": "test-doc2.md", "title": "备案要求", "content": "备案材料与流程说明" * 20,
         "hits": 0.70, "char_len": 280, "importance": 0.3, "fetched_at": ""},
    ]


def test_compaction_e2e_via_400(tmp_path):
    """400 → 压缩审计 start → 重发 → end 配对; 重发 messages 为压缩后内容。"""
    import json

    import scripts.compliance_qa as cqa
    from pulse.llm_audit import _audit_path

    # 调用序列: handoff 摘要(200) → 主调用(400 too long) → 压缩重发(200)
    seq = [
        _fake_resp(200, "会话摘要: 任务进行中, 下一步备案"),
        _fake_resp(400, "prompt_is_too_long"),
        _fake_resp(200, "压缩后正常回答: 备案要求是完成备案并持续合规"),
    ]
    history = [{"role": "user" if i % 2 == 0 else "assistant",
                "content": f"历史消息内容{i}" * 40} for i in range(8)]

    with patch("httpx.post", side_effect=seq), \
         patch.object(cqa, "retrieve", return_value=_fake_chunks()), \
         patch.object(cqa, "_get_api_key", return_value="test-key"):  # CI 无 key → 模拟有 key
        out = cqa.answer("算法备案的要求是什么？", top_k=3, use_cache=False, history=history)

    assert "压缩后正常回答" in out        # 重发成功路径生效
    assert "未找到" not in out

    # 审计链断言 (过滤 handoff 摘要压缩, 聚焦 400 触发的压缩)
    lines = [json.loads(l) for l in _audit_path().read_text(encoding="utf-8").splitlines()]
    starts = [e for e in lines if e.get("kind") == "compaction/start"
              and e.get("trigger") == "prompt_is_too_long"]
    ends = [e for e in lines if e.get("kind") == "compaction/end"]
    assert len(starts) == 1                           # 生产触发压缩被完整审计
    assert starts[0]["dropped_count"] >= 1            # 早期历史被折叠
    assert any(e["compaction_id"] == starts[0]["compaction_id"] and e["ok"] is True
               for e in ends)                         # start 有配对 end

    # 重发请求记录 = 压缩后的有效历史 (方案 A 重建语义)
    retry = [e for e in lines if e.get("kind") == "request"
             and e.get("source") == "compliance_qa._llm_call_with_retry"]
    assert len(retry) == 1
    assert len(retry[0]["messages"]) == 9           # system + POST_COMPACT_RULES + 6 keep + 当前问题
    assert retry[0]["messages"][1]["role"] == "system"


def test_compaction_e2e_retry_failure_orphan_free(tmp_path):
    """重发失败 (500) → 审计 end 记录失败, 无孤儿 (链仍完整)。"""
    import json

    import scripts.compliance_qa as cqa
    from pulse.llm_audit import _audit_path

    seq = [
        _fake_resp(200, "会话摘要内容"),
        _fake_resp(400, "prompt_is_too_long"),
        _fake_resp(500, "internal error"),
    ]
    history = [{"role": "user" if i % 2 == 0 else "assistant",
                "content": f"历史消息内容{i}" * 40} for i in range(8)]

    with patch("httpx.post", side_effect=seq), \
         patch.object(cqa, "retrieve", return_value=_fake_chunks()), \
         patch.object(cqa, "_get_api_key", return_value="test-key"):
        out = cqa.answer("算法备案的要求是什么？", top_k=3, use_cache=False, history=history)

    assert "压缩重试失败" in out          # 降级消息
    lines = [json.loads(l) for l in _audit_path().read_text(encoding="utf-8").splitlines()]
    starts = [e for e in lines if e.get("kind") == "compaction/start"
              and e.get("trigger") == "prompt_is_too_long"]
    ends = [e for e in lines if e.get("kind") == "compaction/end"]
    assert len(starts) == 1
    assert any(e["compaction_id"] == starts[0]["compaction_id"] and e["ok"] is False
               and e["error"] == "compact_retry_failed" for e in ends)
    # 孤儿检测: 所有 start 都有配对 end
    all_starts = [e for e in lines if e.get("kind") == "compaction/start"]
    end_ids = {e["compaction_id"] for e in ends}
    assert all(e["compaction_id"] in end_ids for e in all_starts)

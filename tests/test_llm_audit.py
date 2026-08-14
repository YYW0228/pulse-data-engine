"""
tests/test_llm_audit.py — Model-visible = Logged 审计链路测试

覆盖: audited_post 落盘 (mock 网络) / 可重建性判定 / 循环检测 / 时间窗口过滤。
"""

from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest

import pulse.llm_audit as la
import scripts.audit_reconstruct as ar

MSG = [{"role": "user", "content": "算法备案要求是什么?"}]


@pytest.fixture(autouse=True)
def _tmp_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(la, "AUDIT_PATH", tmp_path / "llm_audit.jsonl")
    monkeypatch.setattr(ar, "AUDIT_PATH", tmp_path / "llm_audit.jsonl")


def _mock_resp(status: int = 200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {"choices": [{"message": {"content": '{"verdict":"approved"}'}}]}
    return r


def test_audited_post_records_request_before_call(tmp_path):
    """调用前完整落盘请求 (含 messages 全量) — 不变量核心。"""
    with patch("httpx.post", return_value=_mock_resp()) as mock_post:
        la.audited_post("https://api.deepseek.com/v1/chat/completions",
                        headers={"Authorization": "Bearer k"},
                        json={"model": "deepseek-chat", "messages": MSG},
                        source="test.audited_post")

    mock_post.assert_called_once()
    lines = (la.AUDIT_PATH).read_text(encoding="utf-8").strip().splitlines()
    req = json.loads(lines[0])
    assert req["kind"] == "request"
    assert req["messages"] == MSG                      # 模型所见已记录
    assert req["reconstructable"] is True
    assert req["prompt_hash"] == ar._prompt_hash(MSG)
    res = json.loads(lines[1])
    assert res["kind"] == "result" and res["ok"] is True
    assert res["ts_epoch"] > 0


def test_audit_failure_does_not_block_business(tmp_path):
    """网络失败也记录 result, 且异常向上抛 (业务语义不变)。"""
    with patch("httpx.post", side_effect=RuntimeError("conn refused")), pytest.raises(RuntimeError):
        la.audited_post("http://x", json={"model": "m", "messages": MSG})
    lines = (la.AUDIT_PATH).read_text(encoding="utf-8").strip().splitlines()
    res = json.loads(lines[1])
    assert res["ok"] is False and "conn refused" in res["error"]


def test_reconstructable_detects_gaps():
    ok, missing = ar.reconstructable({"call_id": "1", "ts": "t", "model": "m", "messages": MSG})
    assert ok and not missing
    # 缺字段
    assert not ar.reconstructable({"call_id": "1", "ts": "t", "model": "m"})[0]
    # 空 content = 不可重建
    _, m2 = ar.reconstructable({"call_id": "1", "ts": "t", "model": "m",
                                "messages": [{"role": "user", "content": "  "}]})
    assert "messages[0].content.empty" in m2
    # hash 篡改检测
    _, m3 = ar.reconstructable({"call_id": "1", "ts": "t", "model": "m", "messages": MSG,
                                "prompt_hash": "deadbeef"})
    assert "prompt_hash.mismatch" in m3


def test_find_loops_detects_repeat_burst():
    now = time.time()
    reqs = [{"source": "s1", "prompt_hash": "h1", "ts_epoch": now + i * 30} for i in range(3)]
    assert ar.find_loops(reqs)                          # 3 次 / 60s 窗口内 → 循环
    assert not ar.find_loops(reqs[:2])                  # 2 次不算
    spread = [{"source": "s1", "prompt_hash": "h1", "ts_epoch": now + i * 400} for i in range(3)]
    assert not ar.find_loops(spread)                    # 分散不构成循环


def test_load_window_filter(tmp_path):
    """load 只取窗口内记录; 损坏行静默跳过不炸。"""
    now = time.time()
    p = la.AUDIT_PATH
    p.write_text(
        "\n".join([
            json.dumps({"kind": "request", "ts_epoch": now - 10, "x": 1}),
            "{corrupt",
            json.dumps({"kind": "request", "ts_epoch": now - 10 * 86400, "x": 2}),  # 超窗
        ]) + "\n",
        encoding="utf-8",
    )
    reqs, _ = ar.load(days=1)
    assert [r["x"] for r in reqs] == [1]

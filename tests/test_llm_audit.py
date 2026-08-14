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
    p = tmp_path / "llm_audit.jsonl"
    monkeypatch.setenv("LLM_AUDIT_PATH", str(p))   # _append 动态读 env
    monkeypatch.setattr(ar, "AUDIT_PATH", p)       # audit_reconstruct 用导入值


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
    lines = la._audit_path().read_text(encoding="utf-8").strip().splitlines()
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
    lines = la._audit_path().read_text(encoding="utf-8").strip().splitlines()
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
    p = la._audit_path()
    p.write_text(
        "\n".join([
            json.dumps({"kind": "request", "ts_epoch": now - 10, "x": 1}),
            "{corrupt",
            json.dumps({"kind": "request", "ts_epoch": now - 10 * 86400, "x": 2}),  # 超窗
        ]) + "\n",
        encoding="utf-8",
    )
    reqs, _, _ = ar.load(days=1)
    assert [r["x"] for r in reqs] == [1]


def test_compaction_events_recorded():
    """压缩成为一等审计事件: start 带折叠元数据 (role/len/hash), end 配对。"""
    dropped = [{"role": "user", "content": "早期问题" * 10},
               {"role": "assistant", "content": "早期回答" * 10}]
    cid = la.audit_compaction_start("compliance_qa.answer", "prompt_is_too_long",
                                    dropped, kept_count=8)
    assert cid.startswith("cmp_")
    la.audit_compaction_end(cid, ok=True)

    _, _, events = ar.load(days=1)
    starts = [e for e in events if e.get("kind") == "compaction/start"]
    ends = [e for e in events if e.get("kind") == "compaction/end"]
    assert len(starts) == 1 and len(ends) == 1
    s = starts[0]
    assert s["trigger"] == "prompt_is_too_long"
    assert s["dropped_count"] == 2
    assert s["kept_count"] == 8
    assert s["dropped"][0]["role"] == "user"
    assert len(s["dropped"][0]["hash"]) == 16
    assert s["dropped_total_hash"]
    assert ends[0]["compaction_id"] == cid and ends[0]["ok"] is True
    # 方案 A 重建语义: 折叠元数据 + hash 可解释"哪些被折叠"
    assert ar.find_compaction_orphans(events) == []


def test_compaction_orphan_detected():
    """start 无 end (压缩中途崩溃) → 孤儿, 审计链断裂点被标记。"""
    cid = la.audit_compaction_start("test.compact", "simulated_crash", [{"role": "user", "content": "x"}], 3)
    assert cid
    _, _, events = ar.load(days=1)
    orphans = ar.find_compaction_orphans(events)
    assert len(orphans) == 1
    assert orphans[0]["compaction_id"] == cid
    assert orphans[0]["source"] == "test.compact"
    # 补 end 后孤儿消失
    la.audit_compaction_end(cid, ok=False, error="crash")
    _, _, events2 = ar.load(days=1)
    assert ar.find_compaction_orphans(events2) == []


def test_compaction_chain_end_to_end():
    """400 prompt_is_too_long → 压缩 → 重发: 审计链完整 (start + 压缩后request + end)。

    压缩函数本身强制审计 (compact_and_audit), 调用点不再手动 start。
    """
    import scripts.compliance_qa as cqa

    history = [{"role": r, "content": f"消息{i}" * 50}
               for i in range(10) for r in ("user", "assistant")]
    messages = [{"role": "system", "content": "sys"}] + history + \
               [{"role": "user", "content": "当前问题"}]
    result = cqa._reactive_compact(messages, history)
    assert result is not None
    compacted, dropped, cid = result
    assert len(compacted) == 8                       # system + 6 条 + 当前问题
    assert len(dropped) == len(history) - 6         # 被折叠 = 早期 14 条
    assert all(m["role"] in ("user", "assistant") for m in dropped)
    assert cid.startswith("cmp_")                    # 压缩即审计 (强制副作用)

    # 重发 (与 compliance_qa answer 一致) + end 配对
    with patch("httpx.post", return_value=_mock_resp()):
        la.audited_post("https://api.deepseek.com/v1/chat/completions",
                        json={"model": "deepseek-chat", "messages": compacted},
                        source="compliance_qa._llm_call_with_retry")
    la.audit_compaction_end(cid, ok=True)

    reqs, _, events = ar.load(days=1)
    starts = [e for e in events if e.get("kind") == "compaction/start"]
    ends = [e for e in events if e.get("kind") == "compaction/end"]
    assert len(starts) == 1 and len(ends) == 1 and starts[0]["dropped_count"] == 14
    # 方案 A: 压缩后重发的 request 记录 = 模型实际看到的有效历史
    retry_req = [r for r in reqs if r.get("source") == "compliance_qa._llm_call_with_retry"]
    assert len(retry_req) == 1
    assert len(retry_req[0]["messages"]) == 8       # 与 compacted 一致
    assert ar.find_compaction_orphans(events) == []


def test_handoff_summary_compaction_audited():
    """摘要型压缩 (handoff) 审计: summary hash + 被折叠早期历史映射。"""
    import scripts.compliance_qa as cqa

    history = [{"role": "user" if i % 2 == 0 else "assistant",
                "content": f"轮次{i}内容" * 30} for i in range(30)]
    # 用 mock 的 audited_post 让 handoff 走到成功分支
    fake = _mock_resp()
    fake.json.return_value = {"choices": [{"message": {"content": "任务已完成 80%, 下一步: 备案"}}]}
    with patch("httpx.post", return_value=fake):
        summary = cqa._generate_handoff(history, "test-key", "deepseek-chat", None)
    assert summary and "会话交接摘要" in summary

    _, _, events = ar.load(days=1)
    starts = [e for e in events if e.get("kind") == "compaction/start"
              and e.get("source") == "compliance_qa._generate_handoff"]
    assert len(starts) == 1
    s = starts[0]
    assert s["trigger"] == "handoff_summary"
    assert s["dropped_count"] == 20                  # history[:-10] 被折叠
    assert s["summary_hash"] and len(s["summary_hash"]) == 16
    assert s["summary_preview"] == summary[:200]
    ends = [e for e in events if e.get("kind") == "compaction/end"]
    assert len(ends) == 1 and ends[0]["ok"] is True  # start+end 成对
    assert ar.find_compaction_orphans(events) == []


def _seed_fuse_records(n: int, source: str = "test.fuse", hash_: str | None = None):
    """预写 n 条窗口内同源记录, 模拟高频重复。"""
    hash_ = hash_ or la._prompt_hash(MSG)
    now = time.time()
    lines = [json.dumps({"kind": "request", "source": source, "prompt_hash": hash_,
                         "ts_epoch": now - i * 10}) + "\n" for i in range(n)]
    la._audit_path().write_text("".join(lines), encoding="utf-8")


def test_archive_moves_stale_records():
    """超过保留期的记录 gzip 归档 (原文保留), 主链瘦身。"""
    now = time.time()
    p = la._audit_path()
    p.write_text(
        "\n".join([
            json.dumps({"kind": "request", "ts_epoch": now - 60 * 86400, "x": "old"}),
            json.dumps({"kind": "request", "ts_epoch": now - 10, "x": "fresh"}),
            "{corrupt",  # 损坏行也随归档移走
        ]) + "\n",
        encoding="utf-8",
    )
    n = ar.archive(days=30)
    assert n == 2
    lines = p.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1 and '"x": "fresh"' in lines[0]
    # 归档 gzip 存在且含旧记录
    import glob
    gzs = glob.glob(str(p.parent / "llm_audit_archive" / "llm_audit.*.jsonl.gz"))
    assert gzs
    import gzip
    with gzip.open(gzs[-1], "rt", encoding="utf-8") as f:
        content = f.read()
    assert '"x": "old"' in content


def test_fuse_blocks_repeat_burst():
    """同 prompt 高频 (>=阈值) → LoopGuardError, 且不产生新记录。"""
    _seed_fuse_records(la.FUSE_THRESHOLD)
    with pytest.raises(la.LoopGuardError):
        la.audited_post("http://x", json={"model": "m", "messages": MSG},
                        source="test.fuse")
    lines = la._audit_path().read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == la.FUSE_THRESHOLD          # 被拒调用未落盘


def test_fuse_allows_normal_repeats():
    """低于阈值 (如正常重试) 不熔断。"""
    _seed_fuse_records(la.FUSE_THRESHOLD - 1)
    with patch("httpx.post", return_value=_mock_resp()):
        la.audited_post("http://x", json={"model": "m", "messages": MSG},
                        source="test.fuse")
    lines = la._audit_path().read_text(encoding="utf-8").strip().splitlines()
    reqs = [l for l in lines if '"kind": "request"' in l]
    assert len(reqs) == la.FUSE_THRESHOLD              # seed 4 + 本次 1


def test_fuse_off_env_disables():
    """LLM_AUDIT_FUSE=off 完全关闭熔断 (测试/调试)。"""
    import os
    os.environ["LLM_AUDIT_FUSE"] = "off"
    try:
        _seed_fuse_records(la.FUSE_THRESHOLD + 2)
        with patch("httpx.post", return_value=_mock_resp()):
            la.audited_post("http://x", json={"model": "m", "messages": MSG}, source="test.fuse")
        assert True
    finally:
        os.environ.pop("LLM_AUDIT_FUSE", None)

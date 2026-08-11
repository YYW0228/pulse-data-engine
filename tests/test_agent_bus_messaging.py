"""pulse/agent_bus.py 消息/产物/上下文测试 (文件系统总线)"""

import json
import tempfile
from pathlib import Path

from pulse.agent_bus import AgentBus


def _bus(tmp) -> AgentBus:
    return AgentBus(root=Path(tmp))


def test_send_recv_priority():
    with tempfile.TemporaryDirectory() as tmp:
        bus = _bus(tmp)
        bus.send("dev", "CEO", "实现 RAG 模块", priority="steer")
        bus.send("dev", "PM", "排队消息", priority="followUp")
        msgs = bus.recv("dev")
        assert len(msgs) == 2
        assert msgs[0]["priority"] == "steer"  # steer 优先
        assert msgs[0]["from"] == "CEO"
        # mark_delivered=True → 再次收取为空
        assert bus.recv("dev") == []


def test_recv_other_agent_isolated():
    with tempfile.TemporaryDirectory() as tmp:
        bus = _bus(tmp)
        bus.send("dev", "CEO", "给 dev 的")
        bus.send("ops", "CEO", "给 ops 的")
        assert len(bus.recv("dev")) == 1
        assert bus.pending_count("ops") == 1  # 未收取计数


def test_recv_mark_delivered_false():
    with tempfile.TemporaryDirectory() as tmp:
        bus = _bus(tmp)
        bus.send("dev", "CEO", "保留未读")
        msgs = bus.recv("dev", mark_delivered=False)
        assert len(msgs) == 1
        # 未标记 → 再取仍能收到 (默认 mark_delivered=True)
        msgs2 = bus.recv("dev")
        assert len(msgs2) == 1
        # 已标记 → 不再返回
        assert bus.recv("dev") == []
        assert bus.pending_count("dev") == 0


def test_artifact_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        bus = _bus(tmp)
        path = bus.artifact_put("research", "rag-arch", {"engine": "duckdb"},
                                metadata={"source": "test"})
        assert path.exists()
        got = bus.artifact_get("research", "rag-arch")
        assert got is not None
        assert got["content"]["engine"] == "duckdb"
        assert got["metadata"]["source"] == "test"
        assert bus.artifact_get("research", "missing") is None
        listed = bus.artifact_list("research")
        assert len(listed) == 1
        assert listed[0]["name"] == "rag-arch"
        # 无 kind → 全量
        assert len(bus.artifact_list()) == 1
        # 不存在的 kind → 空
        assert bus.artifact_list("nope") == []


def test_context_upsert():
    with tempfile.TemporaryDirectory() as tmp:
        bus = _bus(tmp)
        bus.context_set("last_build", "ok", updated_by="ci")
        assert bus.context_get("last_build") == "ok"
        bus.context_set("last_build", "fail", updated_by="ci")
        assert bus.context_get("last_build") == "fail"
        assert bus.context_get("never_set") is None
        ctx = bus.context_list()
        assert ctx == {"last_build": "fail"}
        # 恢复
        bus.context_set("last_build", "ok")


def test_oplog_corrupt_line_skipped():
    with tempfile.TemporaryDirectory() as tmp:
        bus = _bus(tmp)
        bus.oplog("collect", agent="a")
        (bus.log_dir / "2026-08-10.jsonl").write_text("{bad json}\n")
        entries = bus.export_oplog()
        assert len(entries) == 1  # 坏行被跳过
        assert all("timestamp" in e for e in entries)


def test_bus_dirs_created():
    with tempfile.TemporaryDirectory() as tmp:
        bus = AgentBus(root=Path(tmp) / "nested" / "bus")
        assert (bus.inbox_dir).exists()
        assert (bus.artifact_dir).exists()
        assert (bus.context_dir).exists()
        assert (bus.log_dir).exists()

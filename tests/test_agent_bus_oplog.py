"""tests/test_agent_bus_oplog.py — OpLog 审计日志测试 (sandbank AgentOp 模式)"""

import json
import tempfile
from pathlib import Path

from pulse.agent_bus import AgentBus


def test_oplog_append_and_export():
    """oplog 写入按日期轮转的 jsonl, export 可读回"""
    with tempfile.TemporaryDirectory() as tmp:
        bus = AgentBus(root=Path(tmp))
        op1 = bus.oplog("collect", agent="boom-monitor", path="data/x.json",
                        payload={"count": 200})
        op2 = bus.oplog("export", agent="boom-monitor", payload={"format": "json"})

        entries = bus.export_oplog()
        assert len(entries) == 2
        assert entries[0]["id"] == op1
        assert entries[0]["action"] == "collect"
        assert entries[1]["action"] == "export"
        # 按时间排序
        assert entries[0]["timestamp"] <= entries[1]["timestamp"]


def test_oplog_filter_by_agent():
    """export_oplog 支持按 agent 过滤"""
    with tempfile.TemporaryDirectory() as tmp:
        bus = AgentBus(root=Path(tmp))
        bus.oplog("collect", agent="boom-monitor")
        bus.oplog("collect", agent="intel-pipeline")

        boom_only = bus.export_oplog(agent="boom-monitor")
        assert len(boom_only) == 1
        assert boom_only[0]["agent"] == "boom-monitor"


def test_oplog_no_secrets_in_payload():
    """oplog 不记录密钥类内容 (payload 由调用方负责, 此处验证 schema 不含默认密钥字段)"""
    with tempfile.TemporaryDirectory() as tmp:
        bus = AgentBus(root=Path(tmp))
        op = bus.oplog("verify", agent="compliance", payload={"query": "gdpr 72h"})
        entries = bus.export_oplog()
        assert len(entries) == 1
        raw = (bus.log_dir / f"{entries[0]['timestamp']}").exists() or True
        # 直接读 jsonl 验证无密钥字段
        log_files = list(bus.log_dir.glob("*.jsonl"))
        assert len(log_files) == 1
        line = json.loads(log_files[0].read_text().strip().splitlines()[0])
        assert "api_key" not in json.dumps(line)
        assert "token" not in json.dumps(line)
        assert op == line["id"]


def test_oplog_rotates_by_date():
    """日志按日期分文件 (模拟跨日)"""
    with tempfile.TemporaryDirectory() as tmp:
        bus = AgentBus(root=Path(tmp))
        bus.oplog("a", agent="x")
        # 手工伪造昨日文件
        yesterday = bus.log_dir / "2026-08-10.jsonl"
        yesterday.write_text(json.dumps({"id": "old", "action": "a",
                                         "agent": "x", "timestamp": 1}) + "\n")
        entries = bus.export_oplog()
        assert len(entries) == 2
        # since 过滤
        today_only = bus.export_oplog(since="2026-08-11")
        assert len(today_only) == 1
        assert today_only[0]["id"] != "old"

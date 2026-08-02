"""pulse/memory.py + parsing.py + task.py + trace.py 测试"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── MemoryStore ───────────────────────────────────────────────────────

def test_memory_write_and_conflict(tmp_path):
    from pulse.memory import MemoryStore

    db = tmp_path / "mem.duckdb"
    store = MemoryStore(db)
    store.con.execute("""
        CREATE TABLE compliance_chunks (
            doc_id INTEGER, doc_name VARCHAR, title VARCHAR, content VARCHAR,
            char_len INTEGER, embedding FLOAT[512], importance FLOAT,
            content_hash VARCHAR, last_access TIMESTAMP
        )
    """)

    h1 = store.write_chunk("doc.md", "节1", "原始内容", [0.1] * 512, 0.8)
    assert h1 == store.con.execute(
        "SELECT content_hash FROM compliance_chunks WHERE doc_name='doc.md'"
    ).fetchone()[0]

    # 冲突检测: 内容变更 → 检测到冲突
    conflicts = store.detect_conflicts([
        {"doc_name": "doc.md", "title": "节1", "content": "修改后的内容"}
    ])
    assert len(conflicts) == 1
    assert conflicts[0]["old_hash"] != conflicts[0]["new_hash"]
    store.close()


def test_memory_forget_policy(tmp_path):
    from pulse.memory import MemoryStore

    db = tmp_path / "mem.duckdb"
    store = MemoryStore(db)
    store.con.execute("""
        CREATE TABLE compliance_chunks (
            doc_id INTEGER, doc_name VARCHAR, title VARCHAR, content VARCHAR,
            char_len INTEGER, embedding FLOAT[512], importance FLOAT,
            content_hash VARCHAR, last_access TIMESTAMP
        )
    """)
    # 低重要性 + 长期未访问 → 应被遗忘
    zero = [0.1] * 512
    store.con.execute(
        "INSERT INTO compliance_chunks VALUES (1,'a.md','低价值','x',1,?,0.1,'h1', now() - INTERVAL 200 DAY)",
        [zero],
    )
    store.con.execute(
        "INSERT INTO compliance_chunks VALUES (2,'b.md','高价值','y',1,?,0.9,'h2', now() - INTERVAL 200 DAY)",
        [zero],
    )
    forgotten = store.apply_forget_policy(min_importance=0.3, max_age_days=180)
    assert forgotten == 1  # 只遗忘低价值的
    remaining = store.con.execute("SELECT COUNT(*) FROM compliance_chunks").fetchone()[0]
    assert remaining == 1
    store.close()


def test_memory_wal_replay(tmp_path):
    from pulse.memory import MemoryStore

    db = tmp_path / "mem.duckdb"
    store = MemoryStore(db)
    store.con.execute("""
        CREATE TABLE compliance_chunks (
            doc_id INTEGER, doc_name VARCHAR, title VARCHAR, content VARCHAR,
            char_len INTEGER, embedding FLOAT[512], importance FLOAT,
            content_hash VARCHAR, last_access TIMESTAMP
        )
    """)
    store.write_chunk("a.md", "t", "内容", [0.1] * 512, 0.5)
    # replay 不崩溃且返回 0 未完成 (write 都有 write_done)
    assert store.replay_wal() == 0
    store.close()


# ── ComplianceParser ─────────────────────────────────────────────────

def test_parser_json():
    from pulse.parsing import ComplianceParser

    raw = '{"answer": "算法备案需要在提供服务起十个工作日内完成备案手续", "citations": [{"doc": "a.md", "section": "一"}], "confidence": "high"}'
    r = ComplianceParser().parse(raw)
    assert r.fallback is False
    assert r.answer is not None
    assert "十个工作日" in r.answer.answer
    assert r.answer.confidence == "high"
    assert len(r.answer.citations) == 1


def test_parser_markdown():
    from pulse.parsing import ComplianceParser

    raw = "根据规定需要备案 [文档: a.md | 章节: 一]。\n\n引用来源：\n- a.md"
    r = ComplianceParser().parse(raw)
    assert r.fallback is False
    assert r.answer is not None
    assert len(r.answer.citations) == 1
    assert r.answer.citations[0].doc == "a.md"


def test_parser_fallback():
    from pulse.parsing import ComplianceParser

    r = ComplianceParser().parse("简单回答")
    assert r.fallback is True
    assert r.answer is None


def test_parser_low_confidence():
    from pulse.parsing import ComplianceParser

    # 含"未找到" → low
    raw = "资料中未找到相关内容 [文档: a.md | 章节: 一]"
    r = ComplianceParser().parse(raw)
    assert r.answer is not None
    assert r.answer.confidence == "low"


# ── Task ─────────────────────────────────────────────────────────────

def test_task_from_cli():
    from pulse.task import Task

    t = Task.from_cli("算法备案要求", user="test")
    assert t.source == "cli"
    assert t.intent == "算法备案要求"
    assert t.task_id


def test_task_from_api_and_webhook():
    from pulse.task import Task

    t = Task.from_api({"query": "合规", "domain": "compliance"}, api_key="k")
    assert t.source == "api"
    assert t.domain == "compliance"

    w = Task.from_webhook({"type": "ticket.created", "data": {"id": 1}})
    assert w.source == "webhook"
    assert w.payload["event_data"]["id"] == 1


def test_task_intent_required():
    from pydantic import ValidationError

    from pulse.task import Task

    with pytest.raises(ValidationError):
        Task.from_api({"query": "   "})


# ── Tracer ───────────────────────────────────────────────────────────

def test_tracer_roundtrip(tmp_path, monkeypatch):
    from pulse import trace as trace_mod

    monkeypatch.setattr(trace_mod, "TRACE_PATH", tmp_path / "traces.jsonl")

    from pulse.trace import Tracer

    tracer = Tracer("测试问题", source="test")
    tracer.step("retrieve", {"chunks": 3})
    tracer.step("route", {"model": "deepseek-chat"})
    tracer.save({"success": True, "model": "deepseek-chat"})

    # tail 能找到
    entries = trace_mod.tail(5)
    assert len(entries) == 1
    assert entries[0]["query"] == "测试问题"
    assert len(entries[0]["steps"]) == 2

    # replay 按 run_id
    r = trace_mod.replay(entries[0]["run_id"])
    assert r is not None
    assert r["result"]["success"] is True


# ── PrefixCache 稳定化 ──────────────────────────────────────────────

def test_prefix_cache_messages_structure():
    """messages 结构: system(稳定) + history(append) + 当前(变体)"""
    from experiments.prefix_cache import STABLE_SYSTEM_PROMPT, build_messages

    history = [
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "第一答"},
    ]
    msgs = build_messages("第二问", "检索块", history)
    assert msgs[0]["role"] == "system"  # 稳定前缀
    assert msgs[0]["content"] == STABLE_SYSTEM_PROMPT
    assert len(msgs) == 4  # system + 2 history + 1 current
    assert msgs[-1]["content"].startswith("参考资料:")
    assert "第二问" in msgs[-1]["content"]


def test_prefix_cache_shape_stable():
    """同一 system prompt + 版本 → hash 稳定"""
    from experiments.prefix_cache import STABLE_SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION, prefix_shape

    h1 = prefix_shape(STABLE_SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION)
    h2 = prefix_shape(STABLE_SYSTEM_PROMPT, SYSTEM_PROMPT_VERSION)
    assert h1 == h2  # 稳定
    # 版本变化 → hash 变 (强制缓存失效)
    h3 = prefix_shape(STABLE_SYSTEM_PROMPT, "v2.0")
    assert h1 != h3


def test_prefix_cache_hit_rate_grows():
    """多轮对话缓存命中率递增 (append-only)"""
    from experiments.prefix_cache import build_messages, estimate_cached_tokens

    history: list[dict[str, str]] = []
    rates = []
    for turn in range(1, 5):
        msgs = build_messages(f"问题{turn}", f"检索{turn}", history)
        stats = estimate_cached_tokens(msgs)
        rates.append(stats["hit_rate"])
        history.append({"role": "user", "content": f"问题{turn}"})
        history.append({"role": "assistant", "content": f"回答{turn}"})

    assert rates[0] == 0.0        # 第一轮无缓存
    assert rates[1] > 80          # 第二轮起高命中
    assert rates[2] >= rates[1]   # 递增
    assert rates[3] >= rates[2]

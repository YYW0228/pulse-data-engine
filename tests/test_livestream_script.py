"""scripts/livestream_script.py 测试 — 直播口播脚本生成 (零 LLM)"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.livestream_script import build_script, load_insight, load_signals


def test_build_script_quote_format():
    signals = [
        {"handle": "a", "domain": "x.com", "signal_text": "第一个信号"},
        {"handle": "b", "domain": "x.com", "signal_text": "第二个信号"},
    ]
    out = build_script(signals, "", "2026-08-12")
    assert "@a" in out and "(x.com)" in out
    assert "@b" in out and "(x.com)" in out
    assert "第一个信号" in out
    assert "第二个信号" in out


def test_build_script_ordering():
    signals = [
        {"handle": "alice", "domain": "x.com", "signal_text": "信号A"},
        {"handle": "bob", "domain": "x.com", "signal_text": "信号B"},
        {"handle": "carol", "domain": "x.com", "signal_text": "信号C"},
    ]
    out = build_script(signals, "", "2026-08-12")
    assert out.index("@alice") < out.index("@bob") < out.index("@carol")


def test_build_script_empty_degrade():
    out = build_script([], "", "2026-08-12")
    assert "暂无大 V 信号" in out
    assert "行动号召" in out
    assert "@" not in out


def test_load_signals_reads_db(tmp_path):
    import duckdb

    db = tmp_path / "signals.duckdb"
    con = duckdb.connect(str(db))
    con.execute(
        "CREATE TABLE market_signals (handle VARCHAR, domain VARCHAR, "
        "signal_text VARCHAR, fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    con.execute(
        "INSERT INTO market_signals (handle, domain, signal_text, fetched_at) VALUES "
        "('old', 'x.com', '旧信号', TIMESTAMP '2026-08-12 09:00:00'), "
        "('new', 'y.com', '新信号', TIMESTAMP '2026-08-12 10:00:00')"
    )
    con.close()

    rows = load_signals(db)
    assert len(rows) == 2
    assert rows[0]["handle"] == "new"  # fetched_at 较新者在前


def test_load_signals_missing_db(tmp_path):
    assert load_signals(tmp_path / "nope.duckdb") == []


def test_main_writes_file(tmp_path, monkeypatch):
    from scripts.livestream_script import main

    out = tmp_path / "out.md"
    monkeypatch.setattr(
        sys, "argv",
        [
            "livestream_script.py",
            "--db", str(tmp_path / "market_signals.duckdb"),
            "--insight-dir", str(tmp_path / "insights"),
            "--out", str(out),
        ],
    )
    main()
    assert out.exists()
    assert "行动号召" in out.read_text(encoding="utf-8")

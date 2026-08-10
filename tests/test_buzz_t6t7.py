"""T6/T7 迁移测试 (buzz 吞噬落地)"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_t7_none_semantics(tmp_path, monkeypatch):
    """T7: token None = 未报告 (不误算成本/均值)"""
    import scripts.compliance_metrics as cm

    monkeypatch.setattr(cm, "METRICS_PATH", tmp_path / "m.jsonl")
    cm.record("正常", 100, 5, 3, 1000, 200, True)
    cm.record("拦截", 10, 0, 0, None, None, True, error="intent:probe")
    cm.record("部分", 50, 3, 2, 1500, None, True)

    lines = [json.loads(l) for l in (tmp_path / "m.jsonl").open()]
    assert lines[1]["tokens_in"] is None
    assert lines[2]["cost_estimate_usd"] is None

    s = cm.summarize()
    assert s["token_report_rate"] == 0.667
    assert abs(s["total_cost_usd"] - lines[0]["cost_estimate_usd"]) < 0.0001
    assert s["avg_tokens_in"] == 1250  # 只算有值的


def test_t6_threshold():
    """T6: HANDOFF_THRESHOLD 定义且为 6 (handoff_earlier 落地, A/B 通过)"""
    import scripts.compliance_qa as cqa

    assert cqa.HANDOFF_THRESHOLD == 6


def test_t6_handoff_degradation(monkeypatch):
    """T6: 摘要失败降级 (无 key → 返回 None)"""
    import scripts.compliance_qa as cqa

    monkeypatch.setattr(cqa, "api_key", None) if hasattr(cqa, "api_key") else None
    result = cqa._generate_handoff(
        [{"role": "user", "content": "x"}], "", "deepseek-chat", None)
    assert result is None

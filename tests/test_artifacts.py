"""pulse/artifacts.py 测试 — 证据包"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_artifact_build_and_markdown(tmp_path, monkeypatch):
    from pulse import artifacts as art_mod

    monkeypatch.setattr(art_mod, "EVIDENCE_OUTPUT_DIR", tmp_path / "artifacts")

    from pulse.artifacts import build_artifact

    art = build_artifact(
        task_id="t1",
        query="问题",
        answer="答案内容",
        citations=[{"doc": "a.md", "section": "一"}],
        evidence=[{"doc": "a.md", "snippet": "片段"}],
        confidence="high",
        guardrails={"intent": "factual_query"},
        cost={"tokens_in": 100, "tokens_out": 50, "ms": 500, "cost_usd": 0.001},
        trace_id="run_1",
    )
    path = art.save()
    assert path.exists()
    md = path.read_text(encoding="utf-8")
    assert "证据包 t1" in md
    assert "a.md" in md
    assert "run_1" in md


def test_artifact_json_output(tmp_path, monkeypatch):
    from pulse import artifacts as art_mod

    monkeypatch.setattr(art_mod, "EVIDENCE_OUTPUT_DIR", tmp_path / "artifacts")

    from pulse.artifacts import build_artifact

    art = build_artifact(task_id="t2", query="q", answer="a")
    d = art.to_dict()
    assert d["task_id"] == "t2"
    assert d["query"] == "q"
    assert d["ts"]  # 自动填时间


def test_artifact_review_included(tmp_path, monkeypatch):
    from pulse import artifacts as art_mod

    monkeypatch.setattr(art_mod, "EVIDENCE_OUTPUT_DIR", tmp_path / "artifacts")

    from pulse.artifacts import build_artifact

    art = build_artifact(
        task_id="t3", query="q", answer="a",
        review={"verdict": "flagged", "issues": ["引用不足"]},
    )
    md = art.to_markdown()
    assert "子代理评审" in md
    assert "flagged" in md

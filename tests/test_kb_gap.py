"""kb_gap 缺口扫描器测试: 分级判定 / 短词跳过 / 报告渲染 (零 LLM, mock 检索)。"""

from __future__ import annotations

import json

import pytest

from scripts import kb_gap


@pytest.fixture(autouse=True)
def _fake_retrieve(monkeypatch):
    """mock compliance_qa.retrieve: 返回按查询名定制的相似度 (不加载真实 embedding)"""
    import scripts.compliance_qa as cqa

    SIMS = {
        "算法备案": 0.58,   # 覆盖 (≥阈值)
        "双轨": 0.48,       # edge (0.40~0.52)
        "不存在主题": 0.30,  # gap (<0.40)
    }

    def fake_retrieve(query: str, top_k: int = 5) -> list[dict]:
        sim = SIMS.get(query, 0.0)
        if sim >= 0.52:
            return [{"doc_name": "doc-a", "hits": sim, "title": "t", "content": "c"}]
        return [{"doc_name": "doc-x", "hits": sim, "title": "t", "content": "c"}]

    monkeypatch.setattr(cqa, "retrieve", fake_retrieve)
    yield


GOLDEN = [
    {"question": "算法备案的要求是什么？", "expect": ["算法备案", "双轨", "K"]},
    {"question": "未知主题问题", "expect": ["不存在主题"]},
]


def test_load_golden(tmp_path):
    """load_golden: 支持 list 与 {questions} 两种结构"""
    p = tmp_path / "g.json"
    p.write_text(json.dumps([{"question": "q", "expect": ["e"]}]))
    assert kb_gap.load_golden(p) == [{"question": "q", "expect": ["e"]}]
    p.write_text(json.dumps({"questions": [{"question": "q2", "expect": ["e2"]}]}))
    assert kb_gap.load_golden(p) == [{"question": "q2", "expect": ["e2"]}]


def test_scan_gap_levels():
    """分级: ≥阈值=覆盖; 0.40~阈值=edge; <0.40=gap; 短词跳过"""
    result = kb_gap.scan_gap(GOLDEN, top_k=5, threshold=0.52)
    by_word = {g["expect_word"]: g for g in result["concept_gaps"]}
    assert by_word["双轨"]["level"] == "edge"
    assert by_word["不存在主题"]["level"] == "gap"
    assert "K" not in by_word  # 短词跳过
    assert result["skipped_short"] == 1
    # 题级: 算法备案题有 edge 缺口 → knowledge; 覆盖词不算缺口
    qgaps = {q["question"]: q for q in result["question_gaps"]}
    assert qgaps["算法备案的要求是什么？"]["missing"] == ["双轨"]
    assert qgaps["未知主题问题"]["missing"] == ["不存在主题"]
    assert result["covered"] == 0


def test_scan_gap_all_covered():
    """期望词全部 ≥ 阈值 → 题级 covered +1"""
    golden = [{"question": "q", "expect": ["算法备案"]}]
    result = kb_gap.scan_gap(golden, top_k=5, threshold=0.52)
    assert result["covered"] == 1
    assert result["question_gaps"] == []


def test_render_report_marks_levels():
    """报告渲染: 分级标记与流程说明存在"""
    result = kb_gap.scan_gap(GOLDEN, top_k=5, threshold=0.52)
    report = kb_gap.render_report(result)
    assert "🔴 gap" in report
    assert "🟡 edge" in report
    assert "kb_refresh --no-scrape" in report  # 流程指引
    assert "pending" in report

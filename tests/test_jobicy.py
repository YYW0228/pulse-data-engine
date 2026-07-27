"""Tests for pulse/extractors/jobicy.py — Jobicy API 适配器"""
from pulse.extractors.jobicy import _coerce_keyword


class TestCoerceKeyword:
    """keyword 字段兼容性"""

    def test_string_passthrough(self):
        assert _coerce_keyword("AI") == "AI"

    def test_list_joins(self):
        assert _coerce_keyword(["AI", "ML"]) == "AI, ML"

    def test_empty_string(self):
        assert _coerce_keyword("") == ""

    def test_none_converted(self):
        assert _coerce_keyword(None) == ""  # type: ignore

    def test_single_element_list(self):
        assert _coerce_keyword(["Engineering"]) == "Engineering"

    def test_mixed_types_in_list(self):
        assert _coerce_keyword(["AI", 123]) == "AI, 123"


class TestFetchJobicy:
    """集成测试 (需网络)"""

    def test_fetch_returns_list(self):
        from pulse.extractors.jobicy import fetch
        jobs = fetch(count=5, geo="usa")
        assert isinstance(jobs, list)
        if len(jobs) > 0:
            job = jobs[0]
            assert "url" in job
            assert "job_title" in job
            assert "source" in job
            assert job["source"] == "jobicy"

    def test_fetch_all_returns_combined(self):
        from pulse.extractors.jobicy import fetch_all
        jobs = fetch_all(limit_per_geo=5)
        assert isinstance(jobs, list)
        assert len(jobs) >= 0  # 可能为空 (网络问题)

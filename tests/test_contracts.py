"""测试: Data Contracts (Pydantic 校验 + DLQ 分流)"""

import pytest

from pulse.schema import RawJobContract


class TestDataContracts:
    """Pydantic 神圣契约测试"""

    def test_valid_job(self):
        """干净数据应通过校验"""
        job = RawJobContract(
            url="https://example.com/job1",
            job_title="AI工程师",
            salary_min_k=20,
            salary_max_k=40,
        )
        assert job.url == "https://example.com/job1"
        assert job.salary_min_k == 20

    def test_salary_string_coercion(self):
        """字符串 '25k' 应被转换为 int 25"""
        job = RawJobContract(
            url="https://example.com/job2",
            job_title="后端开发",
            salary_min_k="25k",
            salary_max_k="50k",
        )
        assert job.salary_min_k == 25
        assert job.salary_max_k == 50

    def test_salary_raw_value(self):
        """原始值 25000 应被归一化为 25k"""
        job = RawJobContract(
            url="https://example.com/job3",
            job_title="数据工程师",
            salary_min_k=25000,
            salary_max_k=50000,
        )
        assert job.salary_min_k == 25
        assert job.salary_max_k == 50

    def test_zero_salary_allowed(self):
        """薪资为 0 表示未标注, 应允许"""
        job = RawJobContract(
            url="https://example.com/job4",
            job_title="实习生",
            salary_min_k=0,
            salary_max_k=0,
        )
        assert job.salary_min_k == 0

    def test_max_less_than_min_rejected(self):
        """max < min 应触发校验错误"""
        with pytest.raises(ValueError, match="薪资区间异常"):
            RawJobContract(
                url="https://example.com/job5",
                job_title="经理",
                salary_min_k=50,
                salary_max_k=30,
            )

    def test_empty_title_rejected(self):
        """空标题 min_length=1 应拒绝"""
        with pytest.raises(ValueError):
            RawJobContract(
                url="https://example.com/job6",
                job_title="",
            )

    def test_short_url_rejected(self):
        """URL 太短应拒绝"""
        with pytest.raises(ValueError):
            RawJobContract(
                url="abc",
                job_title="测试",
            )

    def test_none_salary_allowed(self):
        """薪资为空表示未标注, 应允许"""
        job = RawJobContract(
            url="https://example.com/job7",
            job_title="测试岗",
            salary_min_k=None,
            salary_max_k=None,
        )
        assert job.salary_min_k is None

"""
性能基准测试 (pytest-benchmark)

运行:
  uv run pytest tests/test_performance.py --benchmark-only -v
  uv run pytest tests/test_performance.py --benchmark-histogram
"""
import pytest
from pulse.pipeline import Pipeline
from pulse.schema import RawJobContract


@pytest.fixture
def pipeline():
    p = Pipeline(db_path=":memory:")
    p.init_schema()
    yield p
    p.close()


class TestValidateThroughput:
    """校验吞吐量"""

    def test_contract_validation(self, benchmark):
        """Pydantic 单条校验: 期望 > 1000/s"""
        data = {"url": "https://ex.com/job/1", "job_title": "AI工程师",
                "salary_min_k": 30, "salary_max_k": 50}
        result = benchmark(lambda: RawJobContract(**data))
        assert result.salary_min_k == 30

    def test_batch_validate_1000(self, benchmark, pipeline):
        """批量校验 1000 条: 期望 < 2s"""
        jobs = [{"url": f"https://ex.com/job/{i}", "job_title": f"职位{i}",
                 "salary_min_k": 30, "salary_max_k": 50} for i in range(1000)]

        def validate():
            return pipeline.validate_and_route(jobs)

        result = benchmark(validate)
        assert result["summary"]["total"] == 1000


class TestMergeThroughput:
    """合并吞吐量"""

    def test_merge_100_new(self, benchmark):
        """100 条新记录合并: 期望 < 3s"""
        jobs = [{"url": f"https://ex.com/job/{i}", "job_title": f"职位{i}"}
                for i in range(100)]

        def merge():
            p = Pipeline(db_path=":memory:")
            p.init_schema()
            return p.merge_into_ods(jobs)

        stats = benchmark(merge)
        assert stats["new"] == 100

    def test_merge_1000_new(self, benchmark, pipeline):
        """1000 条新记录合并: 期望 < 10s"""
        jobs = [{"url": f"https://ex.com/job/{i}", "job_title": f"职位{i}"}
                for i in range(1000)]

        def merge():
            p = Pipeline(db_path=":memory:")
            p.init_schema()
            return p.merge_into_ods(jobs)

        result = benchmark(merge)
        assert result["new"] == 1000

    def test_merge_1000_duplicate(self, benchmark, pipeline):
        """1000 条重复合并 (幂等): 期望 < 5s"""
        jobs = [{"url": "https://ex.com/job/1", "job_title": "不变岗位"}
                for _ in range(1000)]

        # 先插入一次
        pipeline.merge_into_ods([jobs[0]])

        stats = benchmark(pipeline.merge_into_ods, jobs)
        assert stats["unchanged"] >= 999


class TestClassificationPerformance:
    """分类性能"""

    def test_classify_1000(self, benchmark):
        """1000 条分类: 期望 < 1s"""
        titles = ["AI工程师", "Python后端", "数据仓库", "合规专家",
                  "产品经理", "DevOps", "前端开发", "技术总监"]
        import random
        batch = [random.choice(titles) for _ in range(1000)]

        def classify_all():
            return [Pipeline.classify(t) for t in batch]

        result = benchmark(classify_all)
        assert len(result) == 1000


class TestFullPipeline:
    """全管道吞吐量"""

    def test_pipeline_100_records(self, benchmark):
        """100 条全流程 (validate→merge→dwd→dws): 期望 < 10s"""
        jobs = [{"url": f"https://ex.com/job/{i}", "job_title": f"职位{i % 10}"}
                for i in range(100)]

        def run():
            p = Pipeline(db_path=":memory:")
            p.init_schema()
            r = p.validate_and_route(jobs)
            if r["passed"]:
                p.merge_into_ods(r["passed"])
                p.refresh_dwd()
                p.refresh_dws()
            return p.verify()

        result = benchmark(run)
        assert result["consistent"]

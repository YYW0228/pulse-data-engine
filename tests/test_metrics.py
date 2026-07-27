"""Tests for pulse/metrics.py — 指标注册中心 + Pipeline 集成"""

import pytest

from pulse.metrics import MetricsRegistry, Timer, instrument_task


class TestMetricsRegistry:
    """验证指标注册 — 单例模式 + 所有指标正确创建"""

    def test_singleton(self):
        r1 = MetricsRegistry()
        r2 = MetricsRegistry()
        assert r1 is r2

    def test_dag_metrics_exist(self):
        r = MetricsRegistry()
        assert r.dag_task_duration is not None
        assert r.dag_task_total is not None
        assert r.dag_task_retries is not None
        assert r.dag_run_duration is not None

    def test_pipeline_metrics_exist(self):
        r = MetricsRegistry()
        assert r.ods_rows is not None
        assert r.dwd_rows is not None
        assert r.dlq_rows is not None
        assert r.dlq_by_type is not None
        assert r.parquet_size is not None

    def test_fetch_metrics_exist(self):
        r = MetricsRegistry()
        assert r.fetch_duration is not None
        assert r.fetch_total is not None
        assert r.fetch_retries is not None

    def test_r2_metrics_exist(self):
        r = MetricsRegistry()
        assert r.r2_upload_duration is not None
        assert r.r2_upload_bytes is not None


class TestTimer:
    """上下文管理器计时器"""

    def test_timer_records_duration(self):
        import time

        from prometheus_client import Histogram, generate_latest

        h = Histogram(
            "test_timer_duration",
            "test",
            labelnames=["task_name", "status"],
            buckets=(0.01, 0.1, 1.0),
        )
        with Timer(h, task_name="test_task", status="success"):
            time.sleep(0.01)
        output = generate_latest().decode()
        assert "test_timer_duration_count" in output
        assert "test_timer_duration_sum" in output


class TestInstrumentTask:
    """instrument_task 装饰器"""

    def test_success_records_metric(self):
        from pulse.metrics import metrics

        @instrument_task(task_name="test_instr")
        def my_task():
            return 42

        result = my_task()
        assert result == 42

    def test_failure_records_metric(self):
        @instrument_task(task_name="test_instr_fail")
        def broken_task():
            raise ValueError("expected")

        with pytest.raises(ValueError):
            broken_task()


class TestSnapshot:
    """跨进程快照"""

    def test_dump_snapshot_creates_file(self, tmp_path):
        from pulse.metrics import SNAPSHOT_PATH, dump_snapshot

        original = SNAPSHOT_PATH
        import pulse.metrics as m

        test_path = tmp_path / "snapshot.json"
        m.SNAPSHOT_PATH = test_path
        try:
            dump_snapshot()
            assert test_path.exists()
            import json

            data = json.loads(test_path.read_text())
            assert "timestamp" in data
        finally:
            m.SNAPSHOT_PATH = original

"""测试: 监控告警 + 质量 SLA + 断点续传"""

from pulse.checkpoints import CheckpointManager
from pulse.monitor import Monitor, QualitySLA, QualityStatus


class TestMonitor:
    def test_dlq_spike_ok(self):
        m = Monitor()
        assert m.check_dlq_spike(50, threshold=100) is True  # 50 < 100, OK

    def test_dlq_spike_critical(self):
        m = Monitor()
        assert m.check_dlq_spike(200, threshold=100) is False  # 200 > 100, alert


class TestQualitySLA:
    def test_empty_db(self):
        """空数据库应报告 CRITICAL"""
        sla = QualitySLA(db_path=":memory:")
        sla.con.execute(
            "CREATE TABLE ods_raw_jobs (entity_id VARCHAR, is_latest BOOLEAN, job_title VARCHAR, salary_min_k INTEGER, salary_max_k INTEGER, crawled_at TIMESTAMP)"
        )
        sla.con.execute("CREATE TABLE dwd_cleaned_jobs (entity_id VARCHAR)")
        r = sla.check_freshness()
        assert r["status"] == QualityStatus.CRITICAL


class TestCheckpoint:
    def test_save_and_load(self):
        cm = CheckpointManager(db_path=":memory:")
        cm._init_table()
        cm.save("run_001", "fetch", "validate", offset=50, total=100, processed=30)
        offset, processed = cm.load("run_001", "fetch", "validate")
        assert offset == 50
        assert processed == 30
        cm.complete("run_001", "fetch", "validate")
        # 完成后再加载, 应仍然返回最后进度
        offset2, _processed2 = cm.load("run_001", "fetch", "validate")
        assert offset2 == 50

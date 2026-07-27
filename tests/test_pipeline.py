"""测试: Pipeline 核心 + SCD Type 2 + DLQ + 分类"""
import pytest, os, tempfile
from pulse.pipeline import Pipeline


@pytest.fixture
def fresh_db(tmp_path):
    """每个测试一个独立 DB 文件, 互不污染"""
    db_path = str(tmp_path / "test.duckdb")
    p = Pipeline(db_path=db_path)
    p.init_schema()
    yield p
    p.close()
    if os.path.exists(db_path):
        os.remove(db_path)


JOB_A = {"url": "https://ex.com/job/a", "job_title": "AI工程师",
         "company_name": "测试", "city": "北京", "salary_min_k": 30, "salary_max_k": 50}

JOB_A_CHANGED = {"url": "https://ex.com/job/a", "job_title": "AI工程师",
                 "company_name": "测试", "city": "北京", "salary_min_k": 35, "salary_max_k": 60}

JOB_B = {"url": "https://ex.com/job/b", "job_title": "后端开发",
         "salary_min_k": 25, "salary_max_k": 45}


class TestSCDType2:
    """SCD Type 2 幂等性"""

    def test_new_insertion(self, fresh_db):
        p = fresh_db
        stats = p.merge_into_ods([JOB_A])
        assert stats["new"] == 1
        v = p.verify()
        assert v["ods_total"] == 1 and v["ods_latest"] == 1

    def test_duplicate_idempotent(self, fresh_db):
        p = fresh_db
        p.merge_into_ods([JOB_A])
        p.merge_into_ods([JOB_A])  # 完全相同, 内容哈希不变
        v = p.verify()
        assert v["ods_total"] == 1  # 不应增加

    def test_salary_change_version_split(self, fresh_db):
        p = fresh_db
        p.merge_into_ods([JOB_A])
        stats = p.merge_into_ods([JOB_A_CHANGED])  # 薪资变化
        assert stats["updated"] == 1
        # 2 个版本: 原始 + 变更
        rows = p.con.execute("SELECT is_latest, salary_min_k FROM ods_raw_jobs WHERE entity_id in (SELECT entity_id FROM ods_raw_jobs LIMIT 1) ORDER BY row_id").fetchall()
        assert len(rows) == 2
        assert rows[0][1] == 30  # 原始: is_latest=False, salary=30
        assert rows[1][1] == 35  # 最新: is_latest=True, salary=35

    def test_multi_entity(self, fresh_db):
        p = fresh_db
        p.merge_into_ods([JOB_A, JOB_B])
        v = p.verify()
        assert v["ods_total"] == 2 and v["ods_latest"] == 2

    def test_dwd_refresh(self, fresh_db):
        p = fresh_db
        p.merge_into_ods([JOB_A, JOB_B])
        n = p.refresh_dwd()
        assert n == 2
        cats = p.con.execute("SELECT DISTINCT category FROM dwd_cleaned_jobs ORDER BY category").fetchall()
        assert len(cats) >= 2


class TestDLQ:
    def test_schema_violation(self, fresh_db):
        p = fresh_db
        bad = [{"url": "x", "job_title": "", "salary_min_k": 30}]
        result = p.validate_and_route(bad)
        assert result["summary"]["failed"] == 1
        assert len(result["violations"]) == 1
        dlq = p.con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0]
        assert dlq >= 1


class TestClassification:
    def test_ai_ml(self):
        assert Pipeline.classify("LLM工程师") == "AI/ML算法"
        assert Pipeline.classify("NLP算法研究员") == "AI/ML算法"
        assert Pipeline.classify("推荐系统工程师") == "AI/ML算法"

    def test_backend(self):
        assert Pipeline.classify("Python后端开发") == "后端/架构"
        assert Pipeline.classify("Java架构师") == "后端/架构"
        assert Pipeline.classify("Golang开发") == "后端/架构"

    def test_governance(self):
        assert Pipeline.classify("合规专家") == "治理/合规"
        assert Pipeline.classify("法务专员") == "治理/合规"

    def test_recommend_system(self):
        assert Pipeline.classify("推荐系统工程师") == "AI/ML算法"

    def test_fallback(self):
        assert Pipeline.classify("某个奇怪的职位") == "其他"

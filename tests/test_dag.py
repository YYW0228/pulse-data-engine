"""测试: DAG 拓扑 + Pipeline 导入"""

from pulse.dag import DAG


def test_dag_topology():
    """DAG 5 任务 + 拓扑排序无循环"""
    dag = DAG(name="test", db_path=":memory:")

    called = []

    @dag.task(name="a", depends_on=[])
    def task_a():
        called.append("a")

    @dag.task(name="b", depends_on=["a"])
    def task_b():
        called.append("b")

    @dag.task(name="c", depends_on=["a"])
    def task_c():
        called.append("c")

    @dag.task(name="d", depends_on=["b", "c"])
    def task_d():
        called.append("d")

    result = dag.run(run_id="test_001")
    assert result["summary"]["success"] == 4
    assert result["summary"]["failed"] == 0
    assert called == ["a", "b", "c", "d"] or called == ["a", "c", "b", "d"]
    dag.close()


def test_circular_dependency_detected():
    """循环依赖应被检测并报错"""
    dag = DAG(name="test_circular", db_path=":memory:")

    @dag.task(name="x", depends_on=["y"])
    def task_x():
        pass

    @dag.task(name="y", depends_on=["x"])
    def task_y():
        pass

    import pytest

    with pytest.raises(ValueError, match="循环依赖"):
        dag.run()
    dag.close()


def test_dependency_failure_skips_downstream():
    """依赖失败 → 下游自动跳过"""
    dag = DAG(name="test_skip", db_path=":memory:")

    @dag.task(name="source", depends_on=[])
    def task_source():
        raise RuntimeError("source failed")

    @dag.task(name="downstream", depends_on=["source"])
    def task_downstream():
        pass

    result = dag.run(run_id="test_skip_001")
    assert result["results"]["source"]["status"] == "failed"
    assert result["results"]["downstream"]["status"] == "skipped"
    dag.close()


def test_consistency_default_compat():
    """不传 consistency 时默认值为 'exclusive-lock', 且正常注册/执行/关闭"""
    dag = DAG(name="test_compat", db_path=":memory:")

    # (1) 验证默认值
    assert dag.consistency == "exclusive-lock", (
        f"期望默认 consistency='exclusive-lock', 实际为 '{dag.consistency}'"
    )

    # (2) 注册并执行简单 task
    executed = []

    @dag.task(name="hello")
    def task_hello():
        executed.append("hello")

    result = dag.run(run_id="compat_001")
    assert result["summary"]["success"] == 1
    assert result["summary"]["failed"] == 0
    assert executed == ["hello"]

    # (3) 清理
    dag.close()


def test_dag_state_persisted():
    """DAG 运行状态应写入 DuckDB (临时 DB, 避免与 8501 服务锁冲突)"""
    import duckdb
    import tempfile
    from pathlib import Path

    duckdb.connect(":memory:")
    with tempfile.TemporaryDirectory() as tmp:
        dag = DAG(name="test_persist", db_path=Path(tmp) / "test.duckdb")

        @dag.task(name="p1", depends_on=[])
        def task_p1():
            pass

        dag.run(run_id="persist_001")
        rows = dag.con.execute("SELECT COUNT(*) FROM dag_runs WHERE run_id='persist_001'").fetchone()[0]
        assert rows >= 1  # at least one task recorded
        dag.close()


def test_lock_conflict_error_message():
    """写锁冲突时 exclusive-lock 包装为 RuntimeError (含 lock/写锁/lsof 关键词),
    consistency='none' 时原样抛出 duckdb.IOException。"""
    import os
    import tempfile
    from unittest.mock import patch

    import duckdb
    import pytest

    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as f:
        db_path = f.name

    try:
        # (1) consistency='exclusive-lock' → RuntimeError with lock keywords
        with patch("duckdb.connect", side_effect=duckdb.IOException("Write lock")):
            with pytest.raises(RuntimeError) as exc_info:
                DAG(name="test_lock", db_path=db_path, consistency="exclusive-lock")
            msg = str(exc_info.value)
            assert any(kw in msg for kw in ("lock", "写锁", "lsof")), (
                f"错误消息应包含 lock/写锁/lsof 关键词，实际: {msg}"
            )

        # (2) consistency='none' → 原样抛出 duckdb.IOException
        with patch("duckdb.connect", side_effect=duckdb.IOException("Write lock")):
            with pytest.raises(duckdb.IOException, match="Write lock"):
                DAG(name="test_lock", db_path=db_path, consistency="none")
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)

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


def test_dag_state_persisted():
    """DAG 运行状态应写入 DuckDB"""
    import duckdb
    con = duckdb.connect(":memory:")
    dag = DAG(name="test_persist")

    @dag.task(name="p1", depends_on=[])
    def task_p1():
        pass

    dag.run(run_id="persist_001")
    rows = dag.con.execute(
        "SELECT COUNT(*) FROM dag_runs WHERE run_id='persist_001'"
    ).fetchone()[0]
    assert rows >= 1  # at least one task recorded
    dag.close()

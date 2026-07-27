"""
pulse/dag.py — 轻量级 DAG 编排引擎

特性:
  - 任务定义: @task 装饰器, 自动注册
  - 依赖解析: 拓扑排序, 失败节点终止下游
  - 状态持久: DuckDB dag_runs 表, 无需外部数据库
  - 重试策略: 可配置 per-task retry + backoff
  - 7x24: cron 调用 run_dag(), 幂等触发
"""
import time, logging, random, traceback
from datetime import datetime
from typing import Callable, Optional
from pathlib import Path

logger = logging.getLogger("pulse.dag")


class Task:
    """DAG 计算节点"""

    def __init__(self, name: str, fn: Callable, depends_on: list[str] = None,
                 max_retries: int = 2, retry_delay: float = 2.0,
                 timeout: int = 300):
        self.name = name
        self.fn = fn
        self.depends_on = depends_on or []
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout

    def __repr__(self):
        return f"Task({self.name}, deps={self.depends_on})"


class DAG:
    """有向无环图 — 任务编排引擎"""

    def __init__(self, name: str, db_path: str | Path = "data/jobs.duckdb"):
        self.name = name
        self.tasks: dict[str, Task] = {}
        self.db_path = Path(db_path)
        import duckdb
        self.con = duckdb.connect(str(self.db_path))
        self._init_state_table()

    def _init_state_table(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS dag_runs (
                run_id VARCHAR,
                dag_name VARCHAR,
                task_name VARCHAR,
                status VARCHAR,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                duration_ms INTEGER,
                error_message VARCHAR,
                retry_count INTEGER DEFAULT 0
            )
        """)
        # Index for quick query
        self.con.execute("CREATE INDEX IF NOT EXISTS idx_dag_run ON dag_runs(run_id)")

    def task(self, name: str = None, depends_on: list[str] = None,
             max_retries: int = 2, retry_delay: float = 2.0):
        """装饰器: 注册为 DAG 任务"""
        def decorator(fn):
            task_name = name or fn.__name__
            self.tasks[task_name] = Task(
                name=task_name, fn=fn,
                depends_on=depends_on or [],
                max_retries=max_retries,
                retry_delay=retry_delay,
            )
            return fn
        return decorator

    def _topological_sort(self) -> list[str]:
        """Kahn 算法: 拓扑排序, 识别循环依赖"""
        in_degree = {name: 0 for name in self.tasks}
        for name, task in self.tasks.items():
            for dep in task.depends_on:
                if dep in in_degree:
                    in_degree[name] = in_degree.get(name, 0) + 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            name = queue.pop(0)
            order.append(name)
            for task_name, task in self.tasks.items():
                if name in task.depends_on:
                    in_degree[task_name] -= 1
                    if in_degree[task_name] == 0:
                        queue.append(task_name)

        if len(order) != len(self.tasks):
            missing = set(self.tasks.keys()) - set(order)
            raise ValueError(f"循环依赖检测: {missing}")
        return order

    def _record_run(self, run_id: str, task_name: str, status: str,
                    started_at: datetime, finished_at: datetime = None,
                    error: str = "", retry_count: int = 0):
        duration = 0
        if finished_at and started_at:
            duration = int((finished_at - started_at).total_seconds() * 1000)
        self.con.execute("""
            INSERT INTO dag_runs (run_id, dag_name, task_name, status,
                started_at, finished_at, duration_ms, error_message, retry_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [run_id, self.name, task_name, status,
              started_at, finished_at or started_at,
              duration, error[:500], retry_count])

    def run(self, run_id: str = None) -> dict:
        """执行 DAG: 拓扑排序 → 逐任务运行 → 失败隔离"""
        if run_id is None:
            run_id = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        order = self._topological_sort()
        results = {}

        logger.info(f"DAG '{self.name}' 启动 ({run_id}), {len(order)} 任务")

        for task_name in order:
            task = self.tasks[task_name]

            # 检查依赖
            deps_ok = all(results.get(dep, {}).get("status") == "success"
                         for dep in task.depends_on)
            if not deps_ok:
                failed_deps = [d for d in task.depends_on
                              if results.get(d, {}).get("status") != "success"]
                started = datetime.now()
                self._record_run(run_id, task_name, "skipped", started,
                                error=f"依赖失败: {failed_deps}")
                results[task_name] = {"status": "skipped", "reason": f"dep_failed:{failed_deps}"}
                logger.warning(f"  ⏭️  {task_name}: 跳过 (依赖 {failed_deps} 未通过)")
                continue

            # 执行 (含重试)
            started = datetime.now()
            last_error = ""
            for attempt in range(task.max_retries + 1):
                try:
                    task.fn()
                    finished = datetime.now()
                    self._record_run(run_id, task_name, "success", started, finished,
                                    retry_count=attempt)
                    results[task_name] = {"status": "success"}
                    logger.info(f"  ✅ {task_name} (attempt {attempt+1})")
                    break
                except Exception as e:
                    last_error = str(e)
                    if attempt < task.max_retries:
                        delay = task.retry_delay * (2 ** attempt)
                        logger.warning(f"  🔄 {task_name}: 重试 ({attempt+1}/{task.max_retries}) "
                                     f"after {delay:.1f}s — {str(e)[:60]}")
                        time.sleep(delay)
                    else:
                        finished = datetime.now()
                        self._record_run(run_id, task_name, "failed", started, finished,
                                        error=last_error, retry_count=attempt)
                        results[task_name] = {"status": "failed", "error": last_error}
                        logger.error(f"  ❌ {task_name}: 失败 ({last_error[:100]})")

        # Summary
        success = sum(1 for r in results.values() if r.get("status") == "success")
        failed = sum(1 for r in results.values() if r.get("status") == "failed")
        skipped = sum(1 for r in results.values() if r.get("status") == "skipped")
        logger.info(f"DAG '{self.name}' 完成: {success}成功/{failed}失败/{skipped}跳过")
        return {"run_id": run_id, "results": results,
                "summary": {"total": len(order), "success": success,
                           "failed": failed, "skipped": skipped}}

    def last_run_status(self) -> list[dict]:
        """最近一次 DAG 执行状态"""
        return self.con.execute("""
            SELECT task_name, status, started_at, duration_ms, error_message, retry_count
            FROM dag_runs
            WHERE run_id = (SELECT run_id FROM dag_runs ORDER BY started_at DESC LIMIT 1)
            ORDER BY started_at
        """).fetchdf().to_dict('records')

    def health(self) -> dict:
        """DAG 健康检查: 最近 5 次运行的成功率"""
        recent = self.con.execute("""
            SELECT run_id, COUNT(*) as tasks,
                   SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as passed,
                   SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed
            FROM dag_runs
            GROUP BY run_id
            ORDER BY MAX(started_at) DESC LIMIT 5
        """).fetchall()
        return {
            "total_runs": len(recent),
            "runs": [{"run_id": r[0], "tasks": r[1], "passed": r[2], "failed": r[3]} for r in recent],
        }

    def close(self):
        self.con.close()

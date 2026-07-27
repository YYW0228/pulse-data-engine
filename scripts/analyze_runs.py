"""
scripts/analyze_runs.py — 从 dag_runs 表分析真实运行数据

基于真实 telemetry 决策 Phase B 埋点优先级。

用法:
  uv run python -m scripts.analyze_runs
  uv run python -m scripts.analyze_runs --last 20
"""

import argparse

import duckdb

DB_PATH = "data/jobs.duckdb"


def analyze(last_n: int = 10):
    con = duckdb.connect(DB_PATH)

    # 检查表是否存在
    tables = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchdf()
    if "dag_runs" not in tables["name"].values:
        print("❌ dag_runs 表不存在。请先运行管道。")
        return

    total_runs = con.execute("SELECT COUNT(DISTINCT run_id) FROM dag_runs").fetchone()[0]
    print(f"\n{'=' * 60}")
    print(f"  Pulse Data Engine — 运行分析 ({total_runs} 次 DAG 运行)")
    print(f"{'=' * 60}\n")

    # ── 1. 每次运行的摘要 ─────────────────────────────────────────
    runs = con.execute(f"""
        SELECT run_id,
               MIN(started_at) as first_start,
               MAX(finished_at) as last_end,
               COUNT(*) as tasks,
               SUM(CASE WHEN status='success' THEN 1 ELSE 0 END) as passed,
               SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed,
               SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) as skipped,
               SUM(duration_ms) as total_duration_ms
        FROM dag_runs
        GROUP BY run_id
        ORDER BY first_start DESC
        LIMIT {last_n}
    """).fetchdf()

    print("📊 最近运行:")
    print(
        f"  {'Run ID':<38} {'状态':<8} {'通过':<6} {'失败':<6} {'总耗时(s)':<10} {'开始时间':<20}"
    )
    print(f"  {'-' * 38} {'-' * 8} {'-' * 6} {'-' * 6} {'-' * 10} {'-' * 20}")
    for _, r in runs.iterrows():
        status = "✅" if r["failed"] == 0 else "❌"
        dur = f"{r['total_duration_ms'] / 1000:.1f}" if r["total_duration_ms"] else "?"
        start = str(r["first_start"])[:19] if r["first_start"] else "?"
        rid = r["run_id"][:36]
        print(f"  {rid:<38} {status:<8} {r['passed']:<6} {r['failed']:<6} {dur:<10} {start:<20}")

    # ── 2. Task 级耗时分布 ───────────────────────────────────────
    print("\n⏱️  Task 耗时分布 (毫秒):")
    tasks = con.execute("""
        SELECT task_name,
               COUNT(*) as runs,
               ROUND(AVG(duration_ms), 1) as avg_ms,
               ROUND(MEDIAN(duration_ms), 1) as p50_ms,
               ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms), 1) as p95_ms,
               ROUND(MAX(duration_ms), 1) as max_ms,
               SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failures,
               SUM(CASE WHEN retry_count > 0 THEN 1 ELSE 0 END) as retries
        FROM dag_runs
        WHERE status != 'skipped'
        GROUP BY task_name
        ORDER BY avg_ms DESC
    """).fetchdf()

    print(
        f"  {'Task':<22} {'运行':<6} {'平均(ms)':<10} {'P50(ms)':<10} {'P95(ms)':<10} {'最大(ms)':<10} {'失败':<6} {'重试':<6}"
    )
    print(f"  {'-' * 22} {'-' * 6} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 10} {'-' * 6} {'-' * 6}")
    for _, t in tasks.iterrows():
        print(
            f"  {t['task_name']:<22} {t['runs']:<6} {t['avg_ms']:<10} {t['p50_ms']:<10} {t['p95_ms']:<10} {t['max_ms']:<10} {t['failures']:<6} {t['retries']:<6}"
        )

    # ── 3. 错误分析 ─────────────────────────────────────────────
    print("\n❌ 错误分析:")
    errors = con.execute("""
        SELECT task_name, error_message, COUNT(*) as cnt
        FROM dag_runs
        WHERE status='failed' AND error_message != ''
        GROUP BY task_name, error_message
        ORDER BY cnt DESC
        LIMIT 10
    """).fetchdf()

    if len(errors) > 0:
        for _, e in errors.iterrows():
            msg = str(e["error_message"])[:80]
            print(f"  {e['task_name']:<18} ×{e['cnt']:<4} {msg}")
    else:
        print("  ✅ 无失败记录")

    # ── 4. DLQ 趋势 ─────────────────────────────────────────────
    dlq_total = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0
    dlq_by_type = con.execute("""
        SELECT error_type, COUNT(*) as cnt
        FROM dlq_jobs
        GROUP BY error_type
        ORDER BY cnt DESC
    """).fetchall()

    print(f"\n⚠️  DLQ: {dlq_total} 条")
    for t, c in dlq_by_type:
        print(f"  {t:<25} {c}")

    # ── 5. 建议 ──────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print("  📌 Phase B 埋点建议 (基于真实数据)")
    print(f"{'=' * 60}")

    # 找最慢的任务
    slowest = tasks.sort_values("avg_ms", ascending=False).iloc[0] if len(tasks) > 0 else None
    if slowest is not None:
        print(
            f"\n  最慢 Task: {slowest['task_name']} (avg={slowest['avg_ms']}ms, p95={slowest['p95_ms']}ms)"
        )

    # 高重试率的任务
    retry_tasks = tasks[tasks["retries"] > 0]
    if len(retry_tasks) > 0:
        print(f"  重试 Task: {', '.join(retry_tasks['task_name'].tolist())}")

    print("""
  推荐埋点优先级:
    H1 - DAG task:  开始/结束 span (duration + status + retry_count)
    H2 - Pipeline:  数据量 (ODS行数/DWD行数/DLQ增量)
    H3 - Fetcher:   请求耗时 + HTTP状态码 + 重试次数
    H4 - R2 sync:   上传耗时 + 文件大小
    H5 - DLQ:       错误类型直方图

  输出端点: /metrics (Prometheus 格式, port 9464)
  日志:     现有 JSONL 追加 trace_id
""")

    con.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="分析 dag_runs 运行数据")
    parser.add_argument("--last", type=int, default=10, help="最近 N 次运行")
    args = parser.parse_args()
    analyze(args.last)

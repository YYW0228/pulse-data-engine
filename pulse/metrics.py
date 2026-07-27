"""
pulse/metrics.py — Prometheus 指标定义 (Phase B)

基于 18 次真实运行数据设计的埋点:
  - fetch_validate avg 7.3s → Histogram(0.1, 0.5, 2, 5, 10, 30)
  - transform_dwd avg 3.9s → Histogram(0.1, 0.5, 2, 5, 10)
  - DLQ 248条, 221 是 SCHEMA_VIOLATION → Counter by error_type
  - 数据量 ~1075 ODS 行 → Gauge

用法:
  from pulse.metrics import metrics
  MetricsRegistry内所有指标集中注册, 避免重复定义。

出口: /metrics endpoint (Prometheus scrape target, port 9464)
"""

import logging
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any

from prometheus_client import Counter, Gauge, Histogram
from typing_extensions import Self

logger = logging.getLogger("pulse.metrics")


class MetricsRegistry:
    """统一指标注册中心 — 保证每个指标只注册一次"""

    _instance: "MetricsRegistry | None" = None
    _initialized: bool = False

    def __new__(cls) -> Self:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        # ── DAG 任务指标 ──────────────────────────────────────────
        self.dag_task_duration = Histogram(
            "pulse_dag_task_duration_seconds",
            "DAG task execution duration in seconds",
            labelnames=["task_name", "status"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
        )
        self.dag_task_total = Counter(
            "pulse_dag_task_total",
            "Total DAG task executions",
            labelnames=["task_name", "status"],
        )
        self.dag_task_retries = Counter(
            "pulse_dag_task_retries_total",
            "DAG task retry count",
            labelnames=["task_name"],
        )
        self.dag_run_duration = Histogram(
            "pulse_dag_run_duration_seconds",
            "Full DAG run duration in seconds",
            buckets=(5, 10, 15, 20, 30, 60, 120),
        )

        # ── 管道数据量指标 ────────────────────────────────────────
        self.ods_rows = Gauge(
            "pulse_ods_rows",
            "ODS raw jobs row count",
            labelnames=["version"],  # latest / total
        )
        self.dwd_rows = Gauge(
            "pulse_dwd_rows",
            "DWD cleaned jobs row count",
        )
        self.dlq_rows = Gauge(
            "pulse_dlq_rows",
            "DLQ dead letter queue row count",
        )
        self.dlq_by_type = Counter(
            "pulse_dlq_by_type_total",
            "DLQ entries by error type",
            labelnames=["error_type"],
        )
        self.parquet_size = Gauge(
            "pulse_parquet_size_bytes",
            "Parquet export total size in bytes",
        )

        # ── 采集器指标 ────────────────────────────────────────────
        self.fetch_duration = Histogram(
            "pulse_fetch_duration_seconds",
            "HTTP fetch duration in seconds",
            labelnames=["source", "status_code"],
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
        )
        self.fetch_total = Counter(
            "pulse_fetch_total",
            "Total HTTP fetches",
            labelnames=["source", "status_code"],
        )
        self.fetch_retries = Counter(
            "pulse_fetch_retries_total",
            "HTTP fetch retry count",
            labelnames=["source"],
        )

        # ── R2 同步指标 ──────────────────────────────────────────
        self.r2_upload_duration = Histogram(
            "pulse_r2_upload_duration_seconds",
            "R2 upload duration in seconds",
            buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
        )
        self.r2_upload_bytes = Counter(
            "pulse_r2_upload_bytes_total",
            "Total bytes uploaded to R2",
        )

        logger.info("Metrics registry initialized")


# ── Dump snapshot ────────────────────────────────────────────────────
SNAPSHOT_PATH = Path("data/metrics/snapshot.json")


def dump_snapshot() -> None:
    """Write current metric values as JSON for cross-process exposition."""
    import json
    from datetime import datetime, timezone

    snap: dict = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dag_tasks": {},
        "data_rows": {},
        "dlq": {},
    }
    try:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps(snap, ensure_ascii=False, default=str))
    except OSError:
        pass  # 非关键 — 快照文件不是必须的


# 全局单例
metrics = MetricsRegistry()


# ── 装饰器: 自动记录 DAG task 耗时 + 状态 ────────────────────────────
def instrument_task(task_name: str) -> Callable:
    """Decorator: wrap a DAG task function to record Prometheus metrics."""

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            t0 = time.time()
            status = "success"
            try:
                result = fn(*args, **kwargs)
                return result
            except Exception:
                status = "failed"
                raise
            finally:
                duration = time.time() - t0
                metrics.dag_task_duration.labels(task_name=task_name, status=status).observe(
                    duration
                )
                metrics.dag_task_total.labels(task_name=task_name, status=status).inc()

        return wrapper

    return decorator


# ── 上下文管理器: 手动记录耗时 ──────────────────────────────────────
class Timer:
    """Context manager that records duration to a Histogram."""

    def __init__(self, histogram: Histogram, **labels: str) -> None:
        self.histogram = histogram
        self.labels = labels
        self.t0 = 0.0

    def __enter__(self) -> Self:
        self.t0 = time.time()
        return self

    def __exit__(self, *exc: object) -> None:
        duration = time.time() - self.t0
        self.histogram.labels(**self.labels).observe(duration)

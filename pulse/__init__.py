"""
pulse — Pulse Data Engine

零成本数据湖引擎: ODS/DWD/DWS 三层数仓 + SCD Type 2 + DLQ + Parquet

公开 API:
  Pipeline        — 三层数仓管道 (validate → merge → transform → aggregate)
  DAG             — 轻量级 DAG 编排 (拓扑排序 + 重试 + 状态持久)
  NetworkFetcher  — 工业级网络抓取 (指数退避 + DLQ 容错)
  BackupManager   — DuckDB 备份 (gzip + Cloudflare R2)
  Monitor         — 监控告警 (Slack/Email + 质量 SLA)
  CheckpointManager — 断点续传
  RawJobContract  — 数据契约 (Pydantic 校验入口)
"""

from pulse.backup import BackupManager
from pulse.checkpoints import CheckpointManager
from pulse.dag import DAG
from pulse.fetcher import FetchResult, NetworkFetcher
from pulse.monitor import AlertLevel, Monitor, QualitySLA, QualityStatus
from pulse.pipeline import Pipeline
from pulse.schema import BatchValidationSummary, ExperienceLevel, RawJobContract

__all__ = [
    "DAG",
    "AlertLevel",
    "BackupManager",
    "BatchValidationSummary",
    "CheckpointManager",
    "ExperienceLevel",
    "FetchResult",
    "Monitor",
    "NetworkFetcher",
    "Pipeline",
    "QualitySLA",
    "QualityStatus",
    "RawJobContract",
]

"""
pulse/assets.py — Dagster 资产定义

将 Pulse 数据管道建模为 Dagster asset graph:
  raw_jobs (外部) → ods_raw_jobs → dwd_cleaned_jobs → dws_skill_agg
                                                       → dws_city_agg
                                                       → parquet_export
                                                       → iceberg_export

每个 asset 包装现有的 Pipeline 类方法，不重写业务逻辑。
零状态: assets 之间通过 DuckDB 数据库共享状态，不需 intra-asset I/O。

用法:
  uv run dagster dev -f pulse/assets.py   # 启动 Dagster UI
  uv run dagster job execute -f pulse/assets.py -j pulse_etl_job  # CLI 执行
"""

import logging

from dagster import Definitions, OpExecutionContext, asset

logger = logging.getLogger("pulse.assets")

DB_PATH = "data/jobs.duckdb"
ICEBERG_PATH = "data/ods_iceberg"


def _get_pipeline():
    """延迟创建 Pipeline 实例 (避免 import 时初始化 DuckDB)"""
    from pulse.pipeline import Pipeline

    return Pipeline(db_path=DB_PATH, iceberg_path=ICEBERG_PATH)


# ── ODS ──────────────────────────────────────────────────────────────


@asset(
    name="ods_raw_jobs",
    description="SCD Type 2 操作数据存储 — 从外部源采集 + 校验 + 合并",
    metadata={"schema": "ods_raw_jobs", "type": "SCD_TYPE_2"},
)
def ods_raw_jobs(context: OpExecutionContext) -> str:
    """采集 → Data Contracts 校验 → SCD Type 2 合并入 ODS"""
    p = _get_pipeline()
    p.init_schema()

    from pulse.extractors import fetch_all as fetch_remotive
    from pulse.extractors.jobicy import fetch_all as fetch_jobicy

    raw = fetch_remotive(limit_per_category=5) + fetch_jobicy(limit_per_geo=15)
    context.log.info(f"采集: {len(raw)} 条 (Remotive + Jobicy)")

    # 合并已有静态数据
    existing = p.con.execute("SELECT * FROM raw_jobs WHERE job_title IS NOT NULL").fetchdf()
    if len(existing) > 0:
        r = p.validate_and_route(existing.to_dict("records"))
        if r["passed"]:
            p.merge_into_ods(r["passed"])

    # 新数据
    result = p.validate_and_route(raw)
    context.log.info(f"校验: {result['summary']['passed']}通过 / {result['summary']['failed']}失败")

    if result["passed"]:
        stats = p.merge_into_ods(result["passed"])
        context.log.info(
            f"ODS: +{stats['new']}新 / {stats['updated']}更新 / {stats['unchanged']}不变"
        )

    v = p.verify()
    context.log.info(f"ODS={v['ods_latest']} DLQ={v['dlq']} 一致={v['consistent']}")
    p.close()
    return f"ods_latest={v['ods_latest']}"


# ── DWD ──────────────────────────────────────────────────────────────


@asset(
    name="dwd_cleaned_jobs",
    description="数据仓库明细 — 清洗 + 分类 + 空值过滤",
    deps=["ods_raw_jobs"],
)
def dwd_cleaned_jobs(context: OpExecutionContext) -> str:
    """从 ODS 最新版本清洗为 DWD"""
    p = _get_pipeline()
    p.init_schema()
    n = p.refresh_dwd()
    context.log.info(f"DWD: {n} 行")
    p.close()
    return f"dwd_rows={n}"


# ── DWS ──────────────────────────────────────────────────────────────


@asset(
    name="dws_skill_agg",
    description="技能分类薪资聚合 — p25/p50/p75 百分位",
    deps=["dwd_cleaned_jobs"],
)
def dws_skill_agg(context: OpExecutionContext) -> str:
    """按职位分类聚合薪资百分位"""
    p = _get_pipeline()
    p.init_schema()
    p.refresh_dws()
    v = p.verify()
    context.log.info(f"DWS: 对账一致={v['consistent']}")
    p.close()
    return f"consistent={v['consistent']}"


@asset(
    name="dws_city_agg",
    description="城市维度岗位聚合",
    deps=["dwd_cleaned_jobs"],
)
def dws_city_agg(context: OpExecutionContext) -> str:
    """按城市聚合岗位数和平均薪资 (由 refresh_dws 一并计算)"""
    p = _get_pipeline()
    p.init_schema()
    p.refresh_dws()
    rows = p.con.execute("SELECT COUNT(*) FROM dws_city_agg").fetchone()[0] or 0
    context.log.info(f"DWS 城市: {rows} 个城市")
    p.close()
    return f"cities={rows}"


# ── 导出 ─────────────────────────────────────────────────────────────


@asset(
    name="parquet_export",
    description="Parquet 冷存储 (Hive 分区, 向后兼容)",
    deps=["ods_raw_jobs"],
)
def parquet_export(context: OpExecutionContext) -> str:
    """导出 ODS 最新版本到 Hive 分区 Parquet"""
    p = _get_pipeline()
    p.init_schema()
    r = p.export_to_parquet()
    context.log.info(f"Parquet: {r['files']} 文件, {r['bytes'] / 1024:.1f} KB")
    p.close()
    return f"files={r['files']}"


@asset(
    name="iceberg_export",
    description="Iceberg 冷存储 (支持 time travel)",
    deps=["ods_raw_jobs"],
)
def iceberg_export(context: OpExecutionContext) -> str:
    """导出 ODS 全量到 Iceberg 格式 (含快照)"""
    p = _get_pipeline()
    p.init_schema()
    r = p.export_to_iceberg()
    snaps = len(r.get("snapshots", []))
    context.log.info(
        f"Iceberg: {r['data_files']} 文件, {r['total_bytes'] / 1024:.1f} KB, {snaps} 快照"
    )
    p.close()
    return f"snapshots={snaps}"


# ── 质量 ─────────────────────────────────────────────────────────────


@asset(
    name="quality_report",
    description="数据质量 SLA 报告 + DLQ 检查",
    deps=["dws_skill_agg", "dws_city_agg", "parquet_export", "iceberg_export"],
)
def quality_report(context: OpExecutionContext) -> dict:
    """执行质量 SLA 检查 + DLQ 告警"""
    from pulse.monitor import AlertLevel, Monitor, QualitySLA

    sla = QualitySLA(DB_PATH)
    report = sla.full_report()
    context.log.info(
        f"质量: 完整={report['completeness']['status']} "
        f"有效={report['validity']['status']} "
        f"新鲜={report['freshness']['status']} "
        f"一致={report['consistency']['status']}"
    )

    # CRITICAL → 告警
    monitor = Monitor()
    issues = []
    for k, v in report.items():
        if isinstance(v, dict) and v.get("status") == "CRITICAL" and k != "timestamp":
            issues.append(f"{k}: {v}")
    for issue in issues:
        monitor.alert(AlertLevel.CRITICAL, "Quality SLA Failed", issue)

    # DLQ
    import duckdb

    con = duckdb.connect(DB_PATH)
    dlq = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0] or 0
    con.close()
    monitor.check_dlq_spike(dlq)

    context.log.info(f"DLQ: {dlq}")
    return {"status": "ok" if not issues else "failed", "dlq": dlq}


# ── 备份 ─────────────────────────────────────────────────────────────


@asset(
    name="backup",
    description="DuckDB 备份 (本地 gzip + R2 远程)",
    deps=["quality_report"],
)
def backup(context: OpExecutionContext) -> str:
    """本地 gzip 压缩 + 远程 R2 备份"""
    from pulse.backup import BackupManager

    bm = BackupManager(r2_bucket="pulse-data-engine-parquet")
    bm.backup_local()
    bm.backup_remote()
    bm.cleanup(keep_last=7)
    context.log.info("备份完成")
    return "ok"


# ── Definitions ──────────────────────────────────────────────────────

defs = Definitions(
    assets=[
        ods_raw_jobs,
        dwd_cleaned_jobs,
        dws_skill_agg,
        dws_city_agg,
        parquet_export,
        iceberg_export,
        quality_report,
        backup,
    ],
)

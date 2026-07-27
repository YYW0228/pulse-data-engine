"""
pulse/runner.py — DAG 任务定义 + 7x24 运行入口

用法:
  uv run python -m pulse.runner              # 单次运行
  uv run python -m pulse.runner --schedule   # 持续调度
"""
import logging, time, sys
from pulse.dag import DAG
from pulse.pipeline import Pipeline
from pulse.logging_config import setup_logging

# JSON 结构化日志 (控制台 + data/logs/pulse.jsonl)
log_file = setup_logging()
logger = logging.getLogger("pulse.runner")

dag = DAG(name="pulse_etl")


@dag.task(name="fetch_validate", depends_on=[])
def task_fetch_validate():
    """采集 → Data Contracts 校验 → ODS"""
    from pulse.extractors import fetch_all as fetch_remotive
    raw = fetch_remotive(limit_per_category=5)
    logger.info(f"采集: {len(raw)} 条")

    p = Pipeline()
    p.init_schema()
    # 先合并已有的 raw_jobs (已有静态数据)
    existing = p.con.execute("SELECT * FROM raw_jobs WHERE job_title IS NOT NULL").fetchdf()
    if len(existing) > 0:
        existing_result = p.validate_and_route(existing.to_dict('records'))
        if existing_result['passed']:
            p.merge_into_ods(existing_result['passed'])

    # 再合并新采集的数据
    result = p.validate_and_route(raw)
    logger.info(f"校验: {result['summary']['passed']}通过 / {result['summary']['failed']}失败")
    if result['passed']:
        stats = p.merge_into_ods(result['passed'])
        logger.info(f"ODS: +{stats['new']}新 / {stats['updated']}更新 / {stats['unchanged']}不变")

    v = p.verify()
    logger.info(f"当前: ODS={v['ods_latest']} DLQ={v['dlq']} 一致={v['consistent']}")
    p.close()


@dag.task(name="transform_dwd", depends_on=["fetch_validate"])
def task_transform_dwd():
    p = Pipeline()
    p.init_schema()
    n = p.refresh_dwd()
    logger.info(f"DWD: {n} 行")
    p.close()


@dag.task(name="aggregate_dws", depends_on=["transform_dwd"])
def task_aggregate_dws():
    p = Pipeline()
    p.init_schema()
    p.refresh_dws()
    v = p.verify()
    logger.info(f"DWS: 对账一致={v['consistent']} DLQ={v['dlq']}")
    p.close()


@dag.task(name="export_parquet", depends_on=["aggregate_dws"])
def task_export_parquet():
    p = Pipeline()
    p.init_schema()
    r = p.export_to_parquet()
    logger.info(f"Parquet: {r['files']} 文件, {r['bytes']/1024:.1f} KB")
    p.close()


@dag.task(name="quality_check", depends_on=["export_parquet"])
def task_quality_check():
    """DAG 末尾执行质量 SLA 检查 + 告警"""
    from pulse.monitor import Monitor, QualitySLA, AlertLevel
    sla = QualitySLA("data/jobs.duckdb")
    report = sla.full_report()
    logger.info(f"质量报告: 完整={report['completeness']['status']} "
                f"有效={report['validity']['status']} "
                f"新鲜={report['freshness']['status']} "
                f"一致={report['consistency']['status']}")

    # 任意一项 CRITICAL → 告警
    monitor = Monitor()
    issues = []
    for k, v in report.items():
        if isinstance(v, dict) and v.get("status") == "CRITICAL":
            if k != "timestamp":
                issues.append(f"{k}: {v}")
    if issues:
        monitor.alert(AlertLevel.CRITICAL, "Quality SLA Failed",
                      "\n".join(str(i) for i in issues))
        raise Exception(f"质量检查失败: {len(issues)} 项 CRITICAL")

    # DLQ 检查
    import duckdb
    con = duckdb.connect("data/jobs.duckdb")
    dlq = con.execute("SELECT COUNT(*) FROM dlq_jobs").fetchone()[0]
    con.close()
    monitor.check_dlq_spike(dlq)


def run_once():
    logger.info("=" * 50)
    logger.info("Pulse Data Engine — DAG 启动")
    logger.info("=" * 50)
    result = dag.run()
    s = result["summary"]
    logger.info(f"结果: {s['success']}成功 / {s['failed']}失败 / {s['skipped']}跳过")
    return result


def run_scheduled(interval: int = 3600):
    logger.info(f"7x24 调度启动, 间隔={interval}s")
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"DAG 崩溃: {e}", exc_info=True)
        logger.info(f"等待 {interval}s 后下一轮...")
        time.sleep(interval)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--schedule":
        run_scheduled(int(sys.argv[2]) if len(sys.argv) > 2 else 3600)
    else:
        run_once()

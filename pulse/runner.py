"""
pulse/runner.py — DAG 任务定义 + 7x24 运行入口

用法:
  python -m pulse.runner                    # 单次运行
  python -m pulse.runner --schedule hourly  # 持续调度
"""

import logging, time, sys
from datetime import datetime
from pulse.dag import DAG
from pulse.pipeline import Pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pulse.runner")

# ── 创建 DAG 实例 ──
dag = DAG(name="pulse_etl")


# ── 任务 1: 数据校验 (validate) ──
@dag.task(name="validate", depends_on=[])
def task_validate():
    """从 raw_jobs 读取, 执行 Data Contracts 校验"""
    p = Pipeline()
    p.init_schema()
    raw = p.con.execute("SELECT * FROM raw_jobs WHERE job_title IS NOT NULL").fetchdf()
    records = raw.to_dict("records")
    logger.info(f"读取 {len(records)} 条原始数据")
    result = p.validate_and_route(records)
    logger.info(
        f"校验: {result['summary']['passed']}通过 / {result['summary']['failed']}失败"
    )
    # 将通过的数据暂存到 pipeline 上下文
    p.close()
    return result


# ── 任务 2: ODS 合并 (merge) ──
@dag.task(name="merge_ods", depends_on=["validate"])
def task_merge_ods():
    p = Pipeline()
    p.init_schema()
    raw = p.con.execute("SELECT * FROM raw_jobs WHERE job_title IS NOT NULL").fetchdf()
    records = raw.to_dict("records")
    # 先校验
    result = p.validate_and_route(records)
    if result["passed"]:
        stats = p.merge_into_ods(result["passed"])
        logger.info(
            f"ODS: +{stats['new']}新 / {stats['updated']}更新 / {stats['unchanged']}不变"
        )
    p.close()


# ── 任务 3: DWD 清洗 (transform) ──
@dag.task(name="transform_dwd", depends_on=["merge_ods"])
def task_transform_dwd():
    p = Pipeline()
    p.init_schema()
    n = p.refresh_dwd()
    logger.info(f"DWD: {n} 行")
    p.close()


# ── 任务 4: DWS 聚合 (aggregate) ──
@dag.task(name="aggregate_dws", depends_on=["transform_dwd"])
def task_aggregate_dws():
    p = Pipeline()
    p.init_schema()
    p.refresh_dws()
    v = p.verify()
    logger.info(f"DWS: 对账一致={v['consistent']} DLQ={v['dlq']}")
    p.close()


# ── 任务 5: Parquet 导出 (export) ──
@dag.task(name="export_parquet", depends_on=["aggregate_dws"])
def task_export_parquet():
    p = Pipeline()
    p.init_schema()
    r = p.export_to_parquet()
    logger.info(f"Parquet: {r['files']} 文件, {r['bytes'] / 1024:.1f} KB")
    p.close()


def run_once():
    """单次 DAG 运行"""
    logger.info("=" * 50)
    logger.info("🚀 Pulse Data Engine — DAG 启动")
    logger.info("=" * 50)
    result = dag.run()
    s = result["summary"]
    logger.info(f"结果: {s['success']}成功 / {s['failed']}失败 / {s['skipped']}跳过")
    if s["failed"] > 0:
        logger.error("DAG 存在失败任务")
    return result


def run_scheduled(interval_seconds: int = 3600):
    """7x24 调度运行"""
    logger.info(f"🔄 7x24 调度启动, 间隔={interval_seconds}s")
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error(f"DAG 崩溃: {e}", exc_info=True)
        logger.info(f"⏳ 等待 {interval_seconds}s 后下一轮...")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--schedule":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 3600
        run_scheduled(interval)
    else:
        run_once()
